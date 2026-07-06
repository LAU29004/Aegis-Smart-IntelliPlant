"""
app/api/routes/upload_routes.py

WHY THIS FILE EXISTS
---------------------
Implements `POST /upload`. WHY this route reads `Content-Length`
BEFORE calling `file.read()`: FastAPI/Starlette will happily buffer an
enormous multipart upload into memory (or a spooled temp file) before
this handler ever gets a chance to reject it based on
`Settings.MAX_UPLOAD_SIZE_MB` - checking the declared `Content-Length`
header first lets an obviously-oversized upload be rejected immediately
via a clean 400, without ever reading its body into memory at all. The
FULL, authoritative size/extension check still happens inside
`app.utils.file_validation.validate_upload` (called by
`DocumentUploadPipelineService.upload_document`) once the actual bytes
are known - streamed clients can lie about `Content-Length`, so this
early check is a fast-path optimization, not a substitute for the real
validation that always runs regardless.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import PipelineStage
from app.core.exceptions import DocumentValidationError
from app.database.session import get_db_session
from app.schemas.converters import upload_result_to_response
from app.schemas.upload_schemas import UploadResponse
from app.services.document_upload_pipeline_service import DocumentUploadPipelineService
from app.api.dependencies import get_upload_pipeline_service

router = APIRouter(tags=["documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest a document",
    description="Accepts a PDF (native-text or scanned) or an image, runs "
    "it through OCR/text extraction, cleaning, chunking, embedding, and "
    "indexes it into both ChromaDB and PostgreSQL.",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="PDF or image file to ingest."),
    department: Optional[str] = Form(default=None, max_length=255),
    equipment_id: Optional[str] = Form(default=None, max_length=255),
    db: Session = Depends(get_db_session),
    upload_pipeline_service: DocumentUploadPipelineService = Depends(get_upload_pipeline_service),
) -> UploadResponse:
    if not file.filename:
        raise DocumentValidationError(
            "Uploaded file has no filename.", stage=PipelineStage.UPLOAD
        )

    # WHY declared Content-Length is checked here, ahead of reading the
    # body: see module docstring. `content_length` may be `None` for
    # some clients/streaming uploads - in that case we simply skip this
    # fast-path check and rely entirely on the authoritative check
    # after reading the actual bytes below.
    settings = upload_pipeline_service.settings
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if int(declared_length) > max_bytes:
            raise DocumentValidationError(
                f"Declared upload size ({int(declared_length) / (1024 * 1024):.1f} MB) "
                f"exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB.",
                stage=PipelineStage.UPLOAD,
                details={"filename": file.filename},
            )

    file_bytes = await file.read()
    result = upload_pipeline_service.upload_document(
        db, file_bytes, file.filename, department=department, equipment_id=equipment_id
    )
    return upload_result_to_response(result)
