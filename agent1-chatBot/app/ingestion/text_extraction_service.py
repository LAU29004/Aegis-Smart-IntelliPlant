"""
app/ingestion/text_extraction_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Text Extraction" stage of the ingestion pipeline
using PyMuPDF (`fitz`) - the ONE place in this codebase that opens a
PDF and reads its native text layer. Critically, this service is also
responsible for DETECTING which pages have little or no extractable
text (i.e. scanned/image-only pages) and flagging them so the
orchestrating `DocumentIngestionService` knows to route exactly those
pages through `OCRService`, rather than OCR-ing an entire document
indiscriminately (which would be both slower and lower quality than
using the native text layer wherever one already exists).
"""

from typing import List

import fitz # PyMuPDF

from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import TextExtractionError
from app.ingestion.schemas import ExtractedPage

# WHY this threshold exists: a page containing only a page number, a
# single header word, or stray whitespace technically has "some" text
# in its native layer, but not enough to be useful - and is exactly
# what a scanned page with a thin OCR-able header would also look
# like. Anything below this many non-whitespace characters is treated
# as "no usable native text" and deferred to OCR instead.
MIN_USABLE_TEXT_CHARACTERS = 20


class TextExtractionService(BaseService):
    """
    Extracts native (non-OCR) text from PDF documents, page by page,
    and flags pages that don't have enough extractable text to be
    considered successfully processed - those pages need OCR.
    """

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> List[ExtractedPage]:
        """
        Extract text from every page of a PDF given as raw bytes.

        WHY bytes rather than a file path: keeps this service
        decoupled from WHERE the file lives (local disk, an in-memory
        upload buffer, or eventually object storage) - the caller
        (`DocumentIngestionService`) is responsible for reading the
        file into memory, this service only knows how to parse PDF
        content.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF file.

        Returns:
            One `ExtractedPage` per page, in order. Pages with fewer
            than `MIN_USABLE_TEXT_CHARACTERS` non-whitespace characters
            of native text have `used_ocr=False` and EMPTY-ish `text`
            here - it is `DocumentIngestionService`'s job to notice
            that and re-extract those specific pages via `OCRService`,
            producing the FINAL `ExtractedPage` with `used_ocr=True`.

        Raises:
            TextExtractionError: if the PDF cannot be opened at all
                (corrupted file, unsupported/encrypted structure).
        """
        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise TextExtractionError(
                "Failed to open PDF for text extraction - the file may be "
                "corrupted or is not a valid PDF.",
                stage=PipelineStage.TEXT_EXTRACTION,
                original_exception=exc,
            ) from exc

        if document.is_encrypted:
            # WHY this is a distinct, explicit error rather than letting
            # `page.get_text()` fail cryptically further down: an
            # encrypted PDF the caller has no password for is a clear,
            # nameable failure mode the uploader needs to understand and
            # act on (re-upload a decrypted copy), not a generic
            # "something went wrong."
            document.close()
            raise TextExtractionError(
                "PDF is password-protected/encrypted and cannot be "
                "processed. Please upload a decrypted version.",
                stage=PipelineStage.TEXT_EXTRACTION,
            )

        pages: List[ExtractedPage] = []
        try:
            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                # WHY `"text"` mode specifically (not "blocks"/"words"/
                # "html"/etc.): this is PyMuPDF's plain reading-order
                # text extraction, the right granularity for feeding
                # into the chunker - richer modes (layout blocks, HTML)
                # would need their own flattening logic here for no
                # benefit to a token-based chunker.
                raw_text = page.get_text("text")
                usable = len(raw_text.strip()) >= MIN_USABLE_TEXT_CHARACTERS
                pages.append(
                    ExtractedPage(
                        page_number=page_index + 1,
                        text=raw_text if usable else "",
                        used_ocr=False,
                    )
                )
        except Exception as exc:
            raise TextExtractionError(
                "Failed while reading text from one or more PDF pages.",
                stage=PipelineStage.TEXT_EXTRACTION,
                details={"pages_processed": len(pages)},
                original_exception=exc,
            ) from exc
        finally:
            document.close()

        self.logger.bind(stage=PipelineStage.TEXT_EXTRACTION.value).info(
            f"Extracted native text from {len(pages)} page(s); "
            f"{sum(1 for p in pages if not p.text)} page(s) need OCR"
        )
        return pages

    def render_page_to_png_bytes(self, pdf_bytes: bytes, page_number: int, dpi: int) -> bytes:
        """
        Rasterize a single PDF page to PNG bytes at the given DPI, for
        handoff to `OCRService`.

        WHY this lives HERE (in the text extraction service) rather
        than inside `OCRService` itself: rendering a PDF PAGE to an
        image is fundamentally a PDF-parsing operation (it needs
        `fitz`/PyMuPDF), not an OCR operation. `OCRService` should stay
        focused purely on "given an image, produce text" and remain
        equally usable for standalone image uploads that were never a
        PDF page to begin with - mixing PDF rendering into it would
        blur that boundary.

        Args:
            pdf_bytes: Raw bytes of the source PDF.
            page_number: 1-indexed page to render.
            dpi: Rasterization resolution (`Settings.OCR_DPI`) - higher
                DPI improves OCR accuracy at the cost of processing time.

        Returns:
            PNG-encoded image bytes for the requested page.

        Raises:
            TextExtractionError: if the page cannot be rendered.
        """
        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            raise TextExtractionError(
                "Failed to open PDF for page rendering.",
                stage=PipelineStage.OCR,
                original_exception=exc,
            ) from exc

        try:
            page = document.load_page(page_number - 1)
            # WHY `dpi=dpi` rather than a fixed zoom matrix: `get_pixmap`
            # accepts DPI directly in modern PyMuPDF, keeping the DPI ->
            # pixel-density relationship explicit and driven straight
            # from `Settings.OCR_DPI` rather than a manually-computed
            # zoom factor that could drift out of sync with that setting.
            pixmap = page.get_pixmap(dpi=dpi)
            return pixmap.tobytes("png")
        except Exception as exc:
            raise TextExtractionError(
                f"Failed to render page {page_number} to an image for OCR.",
                stage=PipelineStage.OCR,
                details={"page_number": page_number, "dpi": dpi},
                original_exception=exc,
            ) from exc
        finally:
            document.close()

    def health_check(self) -> dict:
        """
        Verifies PyMuPDF can construct and read back a trivial
        in-memory PDF, end to end.
        """
        try:
            probe = fitz.open()
            page = probe.new_page()
            page.insert_text((72, 72), "health check probe document text")
            pdf_bytes = probe.tobytes()
            probe.close()

            pages = self.extract_from_pdf_bytes(pdf_bytes)
            healthy = len(pages) == 1 and "health check probe" in pages[0].text
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {"pymupdf_version": fitz.pymupdf_version},
            }
        except TextExtractionError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
