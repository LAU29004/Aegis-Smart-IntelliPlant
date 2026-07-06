"""
app/schemas/document_schemas.py

WHY THIS FILE EXISTS
---------------------
Defines the request/response models for `GET /documents` and
`DELETE /document/{id}`.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import DocumentType
from app.database.enums import DocumentStatus


class DocumentListQueryParams(BaseModel):
    """
    Query parameters for `GET /documents`.

    WHY pagination is included even though the spec's API Design
    section doesn't explicitly call it out: an unbounded `GET
    /documents` against a plant's full document library (potentially
    thousands of manuals/procedures over time) would return an
    unboundedly large response and place unnecessary load on
    PostgreSQL - `limit`/`offset` with a sane default and a hard
    maximum is standard, necessary hygiene for any list endpoint
    backed by a growing table, not scope creep.
    """

    department: Optional[str] = Field(default=None, max_length=255)
    equipment_id: Optional[str] = Field(default=None, max_length=255)
    status: Optional[DocumentStatus] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class DocumentSummaryResponse(BaseModel):
    """One document's summary, as returned in a `GET /documents` listing."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    original_filename: str
    document_type: DocumentType
    department: Optional[str] = None
    equipment_id: Optional[str] = None
    status: DocumentStatus
    total_pages: Optional[int] = None
    total_chunks: int
    error_message: Optional[str] = Field(
        default=None,
        description="Populated only when status is 'failed', explaining why.",
    )
    created_at: datetime


class DocumentListResponse(BaseModel):
    """Response body for `GET /documents`."""

    documents: List[DocumentSummaryResponse]
    total_count: int = Field(
        ..., description="Total documents matching the filters, ignoring pagination."
    )
    limit: int
    offset: int


class DocumentDeleteResponse(BaseModel):
    """Response body for `DELETE /document/{id}`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "deleted": True,
                "message": "Document and all associated chunks removed from "
                "PostgreSQL and ChromaDB.",
            }
        }
    )

    document_id: str
    deleted: bool
    message: str
