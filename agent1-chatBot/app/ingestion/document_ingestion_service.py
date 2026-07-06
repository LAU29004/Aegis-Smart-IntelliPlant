"""
app/ingestion/document_ingestion_service.py

WHY THIS FILE EXISTS
---------------------
Orchestrates the full ingestion pipeline's document-processing stages
- Text Extraction -> OCR (only for pages that need it) -> Cleaning ->
Chunking -> Metadata Extraction - into ONE call. It depends on
`TextExtractionService`, `OCRService`, `TextCleaningService`, and
`ChunkingService`, never re-implementing any of their logic; its only
job is SEQUENCING them correctly and deciding, per page, whether OCR
is needed.

WHY this does NOT call `EmbeddingService`, `VectorStoreService`, or
touch the database: per the spec's Most Important Requirement, this
service must be independently reusable - e.g. a future "document
preview" or "content audit" feature might want extracted, cleaned
chunks WITHOUT paying for embedding or persistence. Keeping ingestion
(get me clean, chunked text) fully decoupled from storage (put it
somewhere) mirrors the exact same separation `RetrievalService`
maintains from the LLM layer.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import DocumentType, PipelineStage
from app.core.exceptions import DocumentValidationError
from app.ingestion.chunking_service import ChunkingService
from app.ingestion.cleaning_service import TextCleaningService
from app.ingestion.ocr_service import OCRService
from app.ingestion.schemas import EnrichedChunkRecord, ExtractedPage, IngestionResult
from app.ingestion.text_extraction_service import TextExtractionService


class DocumentIngestionService(BaseService):
    """
    Turns a raw uploaded file (PDF or image) into metadata-enriched,
    embedding-ready chunks.
    """

    def __init__(
        self,
        settings: Settings,
        text_extraction_service: TextExtractionService,
        ocr_service: OCRService,
        cleaning_service: TextCleaningService,
        chunking_service: ChunkingService,
    ) -> None:
        """
        Args:
            settings: Validated application settings.
            text_extraction_service: Native PDF text extraction +
                page rasterization for OCR handoff.
            ocr_service: Tesseract OCR for scanned pages / images.
            cleaning_service: Text normalization.
            chunking_service: 512/50-token sliding-window chunker.

        WHY every dependency is injected rather than constructed
        internally: identical rationale to `RetrievalService` -
        callers (the upcoming `services/` composition root, or tests)
        control exactly which instances are wired together, and every
        sub-service remains independently testable and independently
        reusable by other agents.
        """
        super().__init__(settings)
        self.text_extraction_service = text_extraction_service
        self.ocr_service = ocr_service
        self.cleaning_service = cleaning_service
        self.chunking_service = chunking_service

    def _extract_pages_with_ocr_fallback(self, pdf_bytes: bytes) -> List[ExtractedPage]:
        """
        Run native text extraction across the whole PDF, then OCR
        ONLY the specific pages that came back without usable text.

        WHY OCR is applied selectively per-page rather than to the
        whole document whenever ANY page needs it: a typical scanned-
        cover-page-plus-native-text document (or vice versa) would
        otherwise pay OCR's higher latency and lower fidelity cost on
        pages that already have a perfectly good native text layer.
        """
        native_pages = self.text_extraction_service.extract_from_pdf_bytes(pdf_bytes)
        final_pages: List[ExtractedPage] = []

        for page in native_pages:
            if page.text:
                final_pages.append(page)
                continue

            self.logger.bind(stage=PipelineStage.OCR.value).info(
                f"Page {page.page_number} has no usable native text - running OCR"
            )
            image_bytes = self.text_extraction_service.render_page_to_png_bytes(
                pdf_bytes, page.page_number, dpi=self.settings.OCR_DPI
            )
            ocr_text = self.ocr_service.extract_text_from_image_bytes(image_bytes)
            final_pages.append(
                ExtractedPage(page_number=page.page_number, text=ocr_text, used_ocr=True)
            )

        return final_pages

    def _clean_and_filter_pages(
        self, pages: List[ExtractedPage]
    ) -> List[Tuple[int, str]]:
        """
        Clean every page's text and drop pages that end up with no
        usable content after cleaning (e.g. a page that was blank, or
        whose OCR output was pure noise that cleaning stripped down to
        nothing).
        """
        cleaned: List[Tuple[int, str]] = []
        for page in pages:
            cleaned_text = self.cleaning_service.clean(page.text)
            if cleaned_text:
                cleaned.append((page.page_number, cleaned_text))
        return cleaned

    def _enrich_chunks(
        self,
        chunk_records,
        *,
        document_name: str,
        document_type: DocumentType,
        department: Optional[str],
        equipment_id: Optional[str],
        upload_date: Optional[str],
    ) -> List[EnrichedChunkRecord]:
        """
        Implements the "Metadata Extraction" pipeline stage: merges
        each chunk-level `ChunkRecord` with the document-level facts
        known by the caller, producing the final `EnrichedChunkRecord`
        list this service returns.

        WHY `upload_date` defaults to "now" (UTC, ISO-8601) when not
        provided: an ingestion call that doesn't explicitly backdate
        an upload (e.g. re-ingesting an old archive) should timestamp
        itself accurately at the moment ingestion actually ran, rather
        than leaving this required citation field null.
        """
        effective_upload_date = upload_date or datetime.now(timezone.utc).isoformat()
        return [
            EnrichedChunkRecord(
                chunk_index=record.chunk_index,
                content=record.content,
                token_count=record.token_count,
                page_number=record.page_number,
                document_name=document_name,
                document_type=document_type.value,
                department=department,
                equipment_id=equipment_id,
                upload_date=effective_upload_date,
            )
            for record in chunk_records
        ]

    def ingest_pdf(
        self,
        pdf_bytes: bytes,
        *,
        document_name: str,
        department: Optional[str] = None,
        equipment_id: Optional[str] = None,
        upload_date: Optional[str] = None,
    ) -> IngestionResult:
        """
        Run the full ingestion pipeline on a PDF file.

        Args:
            pdf_bytes: Raw bytes of the uploaded PDF.
            document_name: Original filename, attached to every chunk
                for citation display.
            department: Optional document-level metadata filter value.
            equipment_id: Optional document-level metadata filter value.
            upload_date: ISO-8601 timestamp; defaults to now (UTC) if
                not provided.

        Returns:
            An `IngestionResult` with every chunk ready for embedding
            and persistence.

        Raises:
            DocumentValidationError: if `pdf_bytes` is empty.
            TextExtractionError / OCRProcessingError / ChunkingError:
                propagated unchanged from the respective sub-services -
                this method deliberately does NOT catch and re-wrap
                them, since each already carries the correct, specific
                `PipelineStage` and `ErrorCode` for exactly where in
                the pipeline it occurred.
        """
        if not pdf_bytes:
            raise DocumentValidationError(
                "Uploaded PDF file is empty.",
                stage=PipelineStage.UPLOAD,
                details={"document_name": document_name},
            )

        pages = self._extract_pages_with_ocr_fallback(pdf_bytes)
        cleaned_pages = self._clean_and_filter_pages(pages)

        if not cleaned_pages:
            raise DocumentValidationError(
                "No usable text could be extracted from this document, even "
                "after OCR - it may be blank, corrupted, or entirely "
                "unreadable content.",
                stage=PipelineStage.CLEANING,
                details={"document_name": document_name, "total_pages": len(pages)},
            )

        chunk_records = self.chunking_service.chunk_pages(cleaned_pages)
        # WHY document_type is determined HERE rather than passed in by
        # the caller: whether a document counts as a plain PDF or a
        # SCANNED_PDF is a fact discovered DURING extraction (did any
        # page need OCR?), not something the uploader can know in
        # advance - deriving it from `ocr_page_count` keeps this
        # classification accurate and automatic.
        ocr_page_count = sum(1 for p in pages if p.used_ocr)
        document_type = (
            DocumentType.SCANNED_PDF if ocr_page_count > 0 else DocumentType.PDF
        )

        enriched_chunks = self._enrich_chunks(
            chunk_records,
            document_name=document_name,
            document_type=document_type,
            department=department,
            equipment_id=equipment_id,
            upload_date=upload_date,
        )

        self.logger.bind(stage=PipelineStage.METADATA_EXTRACTION.value).info(
            f"Ingestion complete for '{document_name}': {len(pages)} page(s), "
            f"{ocr_page_count} via OCR, {len(enriched_chunks)} chunk(s) produced"
        )
        return IngestionResult(
            total_pages=len(pages),
            ocr_page_count=ocr_page_count,
            chunks=enriched_chunks,
        )

    def ingest_image(
        self,
        image_bytes: bytes,
        *,
        document_name: str,
        department: Optional[str] = None,
        equipment_id: Optional[str] = None,
        upload_date: Optional[str] = None,
    ) -> IngestionResult:
        """
        Run the full ingestion pipeline on a standalone image upload
        (a photo of a nameplate, a whiteboard sketch, a scanned
        single-page form, etc.) - always OCR'd, always treated as a
        single "page".

        Args / Returns / Raises: mirror `ingest_pdf`, substituting
        `document_type=DocumentType.IMAGE` unconditionally.
        """
        if not image_bytes:
            raise DocumentValidationError(
                "Uploaded image file is empty.",
                stage=PipelineStage.UPLOAD,
                details={"document_name": document_name},
            )

        ocr_text = self.ocr_service.extract_text_from_image_bytes(image_bytes)
        page = ExtractedPage(page_number=1, text=ocr_text, used_ocr=True)
        cleaned_pages = self._clean_and_filter_pages([page])

        if not cleaned_pages:
            raise DocumentValidationError(
                "No usable text could be extracted from this image via OCR - "
                "it may be blank, illegible, or contain no text at all.",
                stage=PipelineStage.CLEANING,
                details={"document_name": document_name},
            )

        chunk_records = self.chunking_service.chunk_pages(cleaned_pages)
        enriched_chunks = self._enrich_chunks(
            chunk_records,
            document_name=document_name,
            document_type=DocumentType.IMAGE,
            department=department,
            equipment_id=equipment_id,
            upload_date=upload_date,
        )

        self.logger.bind(stage=PipelineStage.METADATA_EXTRACTION.value).info(
            f"Ingestion complete for image '{document_name}': "
            f"{len(enriched_chunks)} chunk(s) produced"
        )
        return IngestionResult(
            total_pages=1,
            ocr_page_count=1,
            chunks=enriched_chunks,
        )

    def health_check(self) -> dict:
        """
        Aggregates the health of every sub-service this orchestrator
        depends on, mirroring `RetrievalService.health_check`.
        """
        sub_checks = {
            "text_extraction_service": self.text_extraction_service.health_check(),
            "ocr_service": self.ocr_service.health_check(),
            "cleaning_service": self.cleaning_service.health_check(),
            "chunking_service": self.chunking_service.health_check(),
        }
        all_healthy = all(check["healthy"] for check in sub_checks.values())
        return {
            "service": self.service_name,
            "healthy": all_healthy,
            "details": sub_checks,
        }
