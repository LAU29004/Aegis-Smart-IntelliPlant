"""
app/ingestion package.

WHY a dedicated `ingestion` package: groups every service involved in
turning a raw uploaded file into clean, chunked, metadata-enriched
text - `TextExtractionService` (PyMuPDF), `OCRService` (Tesseract),
`TextCleaningService`, `ChunkingService`, and the orchestrating
`DocumentIngestionService`. `services/` and `api/` (upcoming folders)
depend ONLY on `DocumentIngestionService` for the "process this
upload" use case; the individual sub-services remain independently
importable for narrower use cases (e.g. Agent 4's Failure Pattern
agent might want just `TextExtractionService` to pull text from a
maintenance report without running full chunking).
"""

from app.ingestion.chunking_service import ChunkingService
from app.ingestion.cleaning_service import TextCleaningService
from app.ingestion.document_ingestion_service import DocumentIngestionService
from app.ingestion.ocr_service import OCRService
from app.ingestion.schemas import (
    ChunkRecord,
    EnrichedChunkRecord,
    ExtractedDocument,
    ExtractedPage,
    IngestionResult,
)
from app.ingestion.text_extraction_service import TextExtractionService

__all__ = [
    "ChunkingService",
    "TextCleaningService",
    "DocumentIngestionService",
    "OCRService",
    "ChunkRecord",
    "EnrichedChunkRecord",
    "ExtractedDocument",
    "ExtractedPage",
    "IngestionResult",
    "TextExtractionService",
]
