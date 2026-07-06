"""
app/utils/file_validation.py

WHY THIS FILE EXISTS
---------------------
Centralizes upload validation against `Settings.ALLOWED_UPLOAD_EXTENSIONS`
and `Settings.MAX_UPLOAD_SIZE_MB`. This closes a real gap: those two
settings existed in `app/config/settings.py` from the very first
folder built, but nothing in the codebase actually enforced
`MAX_UPLOAD_SIZE_MB` until this file - `DocumentUploadPipelineService`
checked the file extension inline but never checked size, meaning an
arbitrarily large upload would previously flow all the way through
OCR/chunking/embedding before failing (if it failed at all) rather
than being rejected immediately. `DocumentUploadPipelineService` now
calls `validate_upload` here as its first step (see the retrofit in
that file), and the upcoming `api/` upload route can ALSO call this
directly against `Content-Length`/filename before ever reading the
full request body into memory, rejecting an oversized upload as early
as possible.

WHY THIS IS IN `utils/` AND NOT A METHOD ON `DocumentUploadPipelineService`
--------------------------------------------------------------------------
This is a pure, stateless function of its inputs (filename, size,
settings) with no model, no database, no external call - exactly the
kind of dependency-free helper `utils/` exists for, reusable by
`api/`'s route layer, `services/`'s orchestration layer, or a test,
without needing to construct a whole `DocumentUploadPipelineService`
just to validate a filename.
"""

from pathlib import Path

from app.config.settings import Settings
from app.core.constants import PipelineStage
from app.core.exceptions import DocumentValidationError


def get_file_extension(filename: str) -> str:
    """
    Return a filename's extension, lowercased, including the leading
    dot (e.g. `"Manual.PDF"` -> `".pdf"`).

    WHY lowercased: extension allow-lists (`Settings.ALLOWED_UPLOAD_EXTENSIONS`)
    are defined in lowercase - without normalizing here, a perfectly
    valid `"Report.PDF"` upload would be incorrectly rejected just
    because of letter casing.
    """
    return Path(filename).suffix.lower()


def validate_upload(filename: str, file_size_bytes: int, settings: Settings) -> None:
    """
    Validate an upload's filename and size against configured limits.

    Args:
        filename: The original uploaded filename.
        file_size_bytes: Size of the uploaded content in bytes.
        settings: Validated application settings - specifically
            `ALLOWED_UPLOAD_EXTENSIONS` and `MAX_UPLOAD_SIZE_MB`.

    Raises:
        DocumentValidationError: if the file is empty, exceeds the
            configured size limit, or has an extension not in the
            allow-list.
    """
    if file_size_bytes <= 0:
        raise DocumentValidationError(
            "Uploaded file is empty.",
            stage=PipelineStage.UPLOAD,
            details={"filename": filename},
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size_bytes > max_bytes:
        raise DocumentValidationError(
            f"Uploaded file ({file_size_bytes / (1024 * 1024):.1f} MB) "
            f"exceeds the maximum allowed size of "
            f"{settings.MAX_UPLOAD_SIZE_MB} MB.",
            stage=PipelineStage.UPLOAD,
            details={
                "filename": filename,
                "file_size_bytes": file_size_bytes,
                "max_size_bytes": max_bytes,
            },
        )

    extension = get_file_extension(filename)
    if extension not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise DocumentValidationError(
            f"File extension '{extension}' is not supported. Allowed: "
            f"{sorted(settings.ALLOWED_UPLOAD_EXTENSIONS)}.",
            stage=PipelineStage.UPLOAD,
            details={"filename": filename, "extension": extension},
        )
