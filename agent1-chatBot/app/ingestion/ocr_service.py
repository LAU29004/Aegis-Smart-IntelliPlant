"""
app/ingestion/ocr_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "OCR if required" stage of the ingestion pipeline
using Tesseract (via `pytesseract`). This is the ONE place in the
codebase that shells out to the Tesseract binary. It is used for two
distinct sources of images:

    1. Scanned PDF pages - rendered to PNG bytes by
       `TextExtractionService.render_page_to_png_bytes` and handed to
       this service.
    2. Standalone image uploads (PNG/JPG/etc.) - passed directly.

Both paths converge on the same `extract_text_from_image_bytes`
method, so OCR behavior (language, config) is identical regardless of
where the image came from.
"""

import io

import pytesseract
from PIL import Image, UnidentifiedImageError

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import OCRProcessingError


class OCRService(BaseService):
    """
    Wraps Tesseract OCR for extracting text from raster images -
    whether rendered from a scanned PDF page or uploaded directly as
    an image file.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        # WHY the tesseract binary path is set once, here, at
        # construction: `pytesseract` looks for the `tesseract` binary
        # on the system PATH by default, which may not match where
        # it's actually installed in a given container image.
        # Explicitly pointing it at `Settings.TESSERACT_CMD_PATH`
        # removes that environment-dependent guesswork.
        pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD_PATH

    def extract_text_from_image_bytes(self, image_bytes: bytes) -> str:
        """
        Run OCR on raw image bytes and return the extracted text.

        Args:
            image_bytes: Raw bytes of a PNG/JPEG/TIFF/BMP image - a
                rendered PDF page or a directly-uploaded image file.

        Returns:
            The OCR'd text, exactly as Tesseract produced it (cleaning
            happens in a later, separate pipeline stage - see
            `cleaning_service.py` - this method's only job is
            extraction).

        Raises:
            OCRProcessingError: if the bytes are not a readable image,
                or if the Tesseract binary itself fails/is missing.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            # WHY `.load()` is forced here: PIL is lazy - `Image.open`
            # doesn't actually read/decode the full image data until
            # something forces it to, so a truncated/corrupted image
            # file could otherwise slip past `Image.open` successfully
            # and only fail later, deep inside Tesseract, with a much
            # less clear error attribution.
            image.load()
        except (UnidentifiedImageError, OSError) as exc:
            raise OCRProcessingError(
                "The provided file could not be read as a valid image.",
                stage=PipelineStage.OCR,
                original_exception=exc,
            ) from exc

        try:
            text = pytesseract.image_to_string(image, lang=self.settings.OCR_LANGUAGE)
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRProcessingError(
                f"Tesseract binary not found at "
                f"'{self.settings.TESSERACT_CMD_PATH}'. Verify "
                f"TESSERACT_CMD_PATH is correctly configured for this "
                f"environment.",
                stage=PipelineStage.OCR,
                original_exception=exc,
            ) from exc
        except Exception as exc:
            raise OCRProcessingError(
                "Tesseract OCR failed while processing the image.",
                stage=PipelineStage.OCR,
                original_exception=exc,
            ) from exc

        self.logger.bind(stage=PipelineStage.OCR.value).debug(
            f"OCR extracted {len(text)} character(s) from image "
            f"({len(image_bytes)} byte source, lang={self.settings.OCR_LANGUAGE})"
        )
        return text

    def health_check(self) -> dict:
        """
        Verifies Tesseract is installed, reachable, and can OCR a
        trivially generated in-memory image, end to end.
        """
        try:
            # WHY generate a real (if tiny/ugly) image with actual text
            # drawn on it, rather than just checking
            # `pytesseract.get_tesseract_version()`: a version check only
            # proves the binary EXISTS, not that the full
            # image-in -> text-out path actually works (missing language
            # data files, broken install, etc.) - the same class of
            # concern as EmbeddingService/RerankerService's health checks
            # doing a real probe encode/predict rather than a shallow
            # existence check.
            from PIL import ImageDraw

            probe_image = Image.new("RGB", (300, 60), color="white")
            draw = ImageDraw.Draw(probe_image)
            draw.text((10, 10), "HEALTH CHECK", fill="black")
            buffer = io.BytesIO()
            probe_image.save(buffer, format="PNG")

            text = self.extract_text_from_image_bytes(buffer.getvalue())
            version = str(pytesseract.get_tesseract_version())
            return {
                "service": self.service_name,
                "healthy": True,
                "details": {
                    "tesseract_version": version,
                    "language": self.settings.OCR_LANGUAGE,
                    "probe_extracted_text": text.strip()[:50],
                },
            }
        except OCRProcessingError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
