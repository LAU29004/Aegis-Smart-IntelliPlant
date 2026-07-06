"""
app/api/routes/query_routes.py

WHY THIS FILE EXISTS
---------------------
Implements `POST /query`. The route handler itself is deliberately
thin: validate via `QueryRequest`, extract the request id already
stamped by `RequestIDMiddleware`, delegate everything to
`QueryPipelineService.answer_query(...)`, and convert the result to
`QueryResponse`. Every actual pipeline decision (retrieval, prompting,
Groq, citations, confidence, follow-ups, persistence, graceful
degradation) already lives in `services/` and below - this file's only
job is the HTTP boundary.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.core.dependencies import get_request_id
from app.database.session import get_db_session
from app.schemas.converters import query_result_to_response
from app.schemas.query_schemas import QueryRequest, QueryResponse
from app.services.query_pipeline_service import QueryPipelineService
from app.api.dependencies import get_query_pipeline_service

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Ask the RAG Copilot a question",
    description="Runs the full retrieval-augmented generation pipeline: "
    "embeds the query, searches indexed documents (optionally filtered by "
    "department/equipment/document type), reranks results, generates a "
    "cited answer with Groq, computes a confidence score, and suggests "
    "follow-up questions.",
)
def submit_query(
    payload: QueryRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    query_pipeline_service: QueryPipelineService = Depends(get_query_pipeline_service),
) -> QueryResponse:
    request_id = get_request_id(request)
    result = query_pipeline_service.answer_query(
        db,
        payload.query,
        request_id=request_id,
        session_id=payload.session_id,
        department=payload.department,
        equipment_id=payload.equipment_id,
        document_type=payload.document_type.value if payload.document_type else None,
    )
    return query_result_to_response(result)
