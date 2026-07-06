"""
app/services/schemas.py

WHY THIS FILE EXISTS
---------------------
`QueryPipelineResult` and `UploadPipelineResult` are the final,
top-level outputs of this folder's two orchestrating services -
`QueryPipelineService` and `DocumentUploadPipelineService`. They are
deliberately plain dataclasses, not Pydantic models: the upcoming
`api/` folder's route handlers are responsible for converting these
into the actual Pydantic response models declared in `app/schemas/`
(the FastAPI-facing boundary). Keeping the orchestration layer's
output framework-agnostic means these services remain callable
directly (e.g. by a test, or by Agent 2/3/4 importing this service
in-process) without any FastAPI/Pydantic dependency at all.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from app.citations.schemas import Citation, RelatedDocument
from app.confidence.schemas import ConfidenceResult
from app.database.enums import DocumentStatus


@dataclass(frozen=True)
class QueryPipelineResult:
    """
    The complete result of running one query through the full RAG
    pipeline - maps directly to the spec's JSON Response fields:
    answer, citations, confidence, followups, related_documents,
    processing_time.

    Attributes:
        answer: The LLM's generated answer, or the spec's exact
            fallback string if retrieval found nothing relevant.
        citations: Sources the answer actually cited inline via `[n]`.
        confidence: Full confidence detail (score, band, and
            supporting signals) - `api/` extracts just `score`/`band`
            for the public response, keeping the rest available for
            logging.
        followups: Up to `Settings.FOLLOWUP_QUESTION_COUNT` suggested
            next questions. Always a list (never None) - empty when
            follow-up generation was skipped or failed, per
            `FollowUpGenerationError`'s documented graceful-degradation
            contract.
        related_documents: Every distinct document retrieval
            considered relevant, regardless of which were specifically
            cited.
        processing_time_seconds: Total pipeline wall-clock time.
        request_id: Correlation id, when available, for tracing this
            result back to logs and the persisted `QueryLog` row.
    """

    answer: str
    citations: List[Citation] = field(default_factory=list)
    confidence: Optional[ConfidenceResult] = None
    followups: List[str] = field(default_factory=list)
    related_documents: List[RelatedDocument] = field(default_factory=list)
    processing_time_seconds: float = 0.0
    request_id: Optional[str] = None


@dataclass(frozen=True)
class UploadPipelineResult:
    """
    The complete result of running one uploaded file through the full
    ingestion pipeline - backs the spec's `POST /upload` response.

    Attributes:
        document_id: The persisted `Document.id` (as a string).
        filename: The stored filename.
        status: Final `DocumentStatus` - `COMPLETED` on success,
            `FAILED` if any stage raised (with `error_message` set on
            the `Document` row itself for detail).
        total_pages: Pages processed (1 for standalone images).
        total_chunks: Chunks produced and embedded.
        ocr_page_count: How many pages required OCR.
    """

    document_id: str
    filename: str
    status: DocumentStatus
    total_pages: int
    total_chunks: int
    ocr_page_count: int
