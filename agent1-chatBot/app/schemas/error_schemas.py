"""
app/schemas/error_schemas.py

WHY THIS FILE EXISTS
---------------------
Documents, for OpenAPI/Swagger purposes, the EXACT error envelope
shape `app/core/exception_handlers.py` actually produces at runtime.
WHY this is a separate, hand-maintained model rather than something
generated automatically from the exception handlers: FastAPI's
OpenAPI schema generation only knows about response models explicitly
declared on route decorators (e.g. `responses={422: {"model":
ErrorResponse}}` in the upcoming `api/` folder) - without this model,
error responses would be entirely undocumented in the generated API
docs, even though `exception_handlers.py` always returns this exact
shape.

CRITICAL: this model's fields MUST stay in sync with
`exception_handlers.py::_build_error_response`'s actual output. If
that function's envelope shape ever changes, this file needs the
matching update - there is no automated enforcement of that
consistency, so it is called out explicitly here as a maintenance
reminder.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """The nested `error` object within an error response."""

    code: str = Field(..., description="Machine-readable error code, e.g. 'GROQ_TIMEOUT'.")
    message: str = Field(..., description="Human-readable explanation, safe to display.")
    stage: Optional[str] = Field(
        default=None, description="Which pipeline stage the error occurred in, if applicable."
    )
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """
    The exact error envelope every failed request returns, per
    `app/core/exception_handlers.py`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "NO_RETRIEVAL_RESULTS",
                    "message": "No relevant information found in indexed documents.",
                    "stage": "vector_search",
                    "details": {"query": "...", "filters": None},
                },
                "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "timestamp": "2026-07-03T10:15:00.123456+00:00",
            }
        }
    )

    error: ErrorDetail
    request_id: Optional[str] = None
    timestamp: datetime
