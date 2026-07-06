"""
app/schemas package.

WHY a dedicated `schemas` package: holds every Pydantic model that
crosses the FastAPI HTTP boundary - request bodies, query parameters,
and response models for all six routes in the spec's API Design
(`POST /upload`, `POST /query`, `GET /documents`, `GET /history`,
`DELETE /document/{id}`, `GET /health`), plus the shared error
envelope shape. `app/api/` (upcoming folder) imports ONLY from here
for its route signatures and response_model declarations - it never
constructs ad-hoc response dicts, keeping the OpenAPI schema FastAPI
generates fully accurate to what the API actually returns.
"""

from app.schemas.converters import query_result_to_response, upload_result_to_response
from app.schemas.document_schemas import (
    DocumentDeleteResponse,
    DocumentListQueryParams,
    DocumentListResponse,
    DocumentSummaryResponse,
)
from app.schemas.error_schemas import ErrorDetail, ErrorResponse
from app.schemas.health_schemas import HealthCheckResponse
from app.schemas.history_schemas import ConversationTurnResponse, HistoryQueryParams, HistoryResponse
from app.schemas.query_schemas import (
    CitationResponse,
    ConfidenceResponse,
    QueryRequest,
    QueryResponse,
    RelatedDocumentResponse,
)
from app.schemas.upload_schemas import UploadMetadata, UploadResponse

__all__ = [
    "query_result_to_response",
    "upload_result_to_response",
    "DocumentDeleteResponse",
    "DocumentListQueryParams",
    "DocumentListResponse",
    "DocumentSummaryResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthCheckResponse",
    "ConversationTurnResponse",
    "HistoryQueryParams",
    "HistoryResponse",
    "CitationResponse",
    "ConfidenceResponse",
    "QueryRequest",
    "QueryResponse",
    "RelatedDocumentResponse",
    "UploadMetadata",
    "UploadResponse",
]
