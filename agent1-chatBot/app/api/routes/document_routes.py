"""
app/api/routes/document_routes.py

WHY THIS FILE EXISTS
---------------------
Implements `GET /documents` and `DELETE /document/{id}`.

WHY `GET /documents` QUERIES THE DATABASE DIRECTLY RATHER THAN GOING
THROUGH A DEDICATED SERVICE METHOD
----------------------------------------------------------------------
This is a simple, read-only, single-table listing with filtering and
pagination - it has no multi-step orchestration, no external service
calls, no error-handling complexity beyond what SQLAlchemy itself
raises (already covered generically by `DatabaseError` via
`get_db_session`). Wrapping it in a dedicated service purely to keep
"all database access behind a service" as a rule would add a layer of
indirection with no actual behavior to justify it. `DELETE
/document/{id}`, by contrast, DOES go through
`DocumentUploadPipelineService.delete_document` because it has genuine
multi-store orchestration complexity (ChromaDB + PostgreSQL) worth
encapsulating - the same reasoning that put deletion in `services/`
rather than here in the first place.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Document
from app.database.session import get_db_session
from app.schemas.document_schemas import (
    DocumentDeleteResponse,
    DocumentListQueryParams,
    DocumentListResponse,
    DocumentSummaryResponse,
)
from app.services.document_upload_pipeline_service import DocumentUploadPipelineService
from app.utils.pagination import apply_pagination
from app.api.dependencies import get_upload_pipeline_service

router = APIRouter(tags=["documents"])


def _document_to_summary(document: Document) -> DocumentSummaryResponse:
    """
    WHY constructed explicitly (field by field) rather than via
    `DocumentSummaryResponse.model_validate(document)`: `Document.id`
    is a `uuid.UUID` on the ORM row but a `str` on the response model -
    Pydantic v2's default (non-strict) validation does not automatically
    coerce a `UUID` into a `str` field, so relying on `model_validate`'s
    automatic attribute mapping here would raise a validation error.
    Building the response explicitly sidesteps that entirely and keeps
    the mapping obvious and predictable rather than depending on
    Pydantic coercion behavior.
    """
    return DocumentSummaryResponse(
        id=str(document.id),
        filename=document.filename,
        original_filename=document.original_filename,
        document_type=document.document_type,
        department=document.department,
        equipment_id=document.equipment_id,
        status=document.status,
        total_pages=document.total_pages,
        total_chunks=document.total_chunks,
        error_message=document.error_message,
        created_at=document.created_at,
    )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List ingested documents",
    description="Returns a paginated, optionally filtered list of documents "
    "in the knowledge base, most recently uploaded first.",
)
def list_documents(
    params: DocumentListQueryParams = Depends(),
    db: Session = Depends(get_db_session),
) -> DocumentListResponse:
    filters = []
    if params.department:
        filters.append(Document.department == params.department.value)
    if params.equipment_id:
        filters.append(Document.equipment_id == params.equipment_id)
    if params.status:
        filters.append(Document.status == params.status)

    base_stmt = select(Document)
    for condition in filters:
        base_stmt = base_stmt.where(condition)

    total_count = db.execute(
        select(func.count()).select_from(base_stmt.subquery())
    ).scalar_one()

    paginated_stmt = apply_pagination(
        base_stmt.order_by(Document.created_at.desc()), params.limit, params.offset
    )
    documents = db.execute(paginated_stmt).scalars().all()

    return DocumentListResponse(
        documents=[_document_to_summary(d) for d in documents],
        total_count=total_count,
        limit=params.limit,
        offset=params.offset,
    )


@router.delete(
    "/document/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document",
    description="Removes a document and all of its chunks from both "
    "PostgreSQL and ChromaDB.",
)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    upload_pipeline_service: DocumentUploadPipelineService = Depends(get_upload_pipeline_service),
) -> DocumentDeleteResponse:
    upload_pipeline_service.delete_document(db, document_id)
    return DocumentDeleteResponse(
        document_id=str(document_id),
        deleted=True,
        message="Document and all associated chunks removed from "
        "PostgreSQL and ChromaDB.",
    )
