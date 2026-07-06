"""
app/schemas/upload_schemas.py

WHY THIS FILE EXISTS
---------------------
Defines the response model for `POST /upload`. WHY there is no
`UploadRequest` Pydantic model here for the file itself: `POST /upload`
is a `multipart/form-data` request (a file plus a few string fields),
which FastAPI handles via `UploadFile` and `Form(...)` parameters
directly in the route signature (upcoming `api/` folder) - NOT via a
JSON-body Pydantic model, since Pydantic models validate JSON bodies,
not multipart form parts. `UploadMetadata` below exists purely to
give those Form(...) fields one documented, reusable shape rather than
scattering their descriptions/constraints across the route signature.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.database.enums import DocumentStatus


class UploadMetadata(BaseModel):
    """
    The non-file form fields accompanying a `POST /upload` request.

    WHY this exists as a standalone model even though FastAPI will
    actually receive these as individual `Form(...)` parameters (not
    as a nested JSON object within the multipart body): it documents
    the exact validation rules (length limits) ONE place, which the
    `api/` route's individual `Form(...)` parameter definitions can
    reference/mirror, keeping the constraints consistent with
    `QueryRequest`'s equivalent `department`/`equipment_id` fields
    rather than independently drifting.
    """

    department: Optional[str] = Field(default=None, max_length=255)
    equipment_id: Optional[str] = Field(default=None, max_length=255)


class UploadResponse(BaseModel):
    """Response body for `POST /upload`."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "filename": "Pump Manual.pdf",
                "status": "completed",
                "total_pages": 12,
                "total_chunks": 34,
                "ocr_page_count": 0,
            }
        },
    )

    document_id: str
    filename: str
    status: DocumentStatus
    total_pages: int
    total_chunks: int
    ocr_page_count: int
