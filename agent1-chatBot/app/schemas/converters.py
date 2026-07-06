"""
app/schemas/converters.py

WHY THIS FILE EXISTS
---------------------
`app/services/query_pipeline_service.py` and
`app/services/document_upload_pipeline_service.py` return plain,
framework-agnostic dataclasses (`QueryPipelineResult`,
`UploadPipelineResult`) - see their module docstrings for why. The
FastAPI routes in the upcoming `api/` folder need Pydantic response
models instead. Rather than scattering ad-hoc `ResponseModel(**dataclasses.asdict(x))`
conversions across every route handler (fragile - a typo'd kwarg name
fails silently different ways depending on the model), this module is
the ONE place that conversion logic lives, so it can be tested once
and reused by every route that needs it.
"""

from app.schemas.query_schemas import (
    CitationResponse,
    ConfidenceResponse,
    QueryResponse,
    RelatedDocumentResponse,
)
from app.schemas.upload_schemas import UploadResponse
from app.services.schemas import QueryPipelineResult, UploadPipelineResult


def query_result_to_response(result: QueryPipelineResult) -> QueryResponse:
    """
    Convert a `QueryPipelineService.answer_query(...)` result into the
    `POST /query` response body.

    WHY `confidence` defaults to a zero/RED `ConfidenceResponse` if
    `result.confidence` is somehow `None`: every real code path through
    `QueryPipelineService` always sets `confidence` (either from
    `ConfidenceEngine.compute(...)` or the explicit RED default in the
    no-results short-circuit path) - `None` should never actually reach
    here. This fallback exists purely as a defensive guard so a future
    bug in `QueryPipelineService` producing a `None` confidence fails
    as a visibly wrong "0, RED" response rather than crashing Pydantic
    validation with an opaque "field required" error at the API
    boundary.
    """
    confidence = (
        ConfidenceResponse(score=result.confidence.score, band=result.confidence.band)
        if result.confidence is not None
        else ConfidenceResponse(score=0.0, band="red")
    )
    return QueryResponse(
        answer=result.answer,
        citations=[CitationResponse.model_validate(c) for c in result.citations],
        confidence=confidence,
        followups=result.followups,
        related_documents=[
            RelatedDocumentResponse.model_validate(d) for d in result.related_documents
        ],
        processing_time=result.processing_time_seconds,
    )


def upload_result_to_response(result: UploadPipelineResult) -> UploadResponse:
    """Convert a `DocumentUploadPipelineService.upload_document(...)` result
    into the `POST /upload` response body."""
    return UploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        status=result.status,
        total_pages=result.total_pages,
        total_chunks=result.total_chunks,
        ocr_page_count=result.ocr_page_count,
    )
