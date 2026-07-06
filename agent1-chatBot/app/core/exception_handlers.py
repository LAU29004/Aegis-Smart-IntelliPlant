"""
app/core/exception_handlers.py

WHY THIS FILE EXISTS
---------------------
Without centralized exception handlers, every route in `app/api/`
would need its own try/except around every service call, duplicating
the same "log it, map it to an HTTP status, shape the JSON body"
logic dozens of times. Instead, routes simply raise one of the typed
exceptions from `core/exceptions.py` (or let a lower layer raise it)
and FastAPI dispatches to exactly one of the handlers registered here.

`register_exception_handlers(app)` is called once from `app/main.py`
(upcoming `api/` folder) at application startup.

Every error response follows ONE consistent envelope:

    {
        "error": {
            "code": "GROQ_TIMEOUT",
            "message": "...",
            "stage": "llm_generation",
            "details": {...}
        },
        "request_id": "a1b2c3d4-...",
        "timestamp": "2026-07-02T10:15:00.123456+00:00"
    }

This consistency is what lets a future Agent Orchestrator (or any
frontend) write ONE error-parsing code path that works identically
regardless of which of the four agents produced the error.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.logging_config import get_logger
from app.core.constants import ErrorCode
from app.core.exceptions import IntelliPlantBaseException

logger = get_logger(__name__)


def _sanitize_validation_errors(errors: list) -> list:
    """
    Strip Pydantic v2's `ctx` key from each validation error dict.

    WHY dropping `ctx` entirely rather than trying to serialize it:
    `ctx` exists for Pydantic's own internal error-message templating
    and, for custom `field_validator` failures specifically, contains
    the raw exception object that was raised - there is no reliable,
    generic way to JSON-serialize an arbitrary exception instance
    (different validators can raise different exception types with
    different constructor signatures). Every error dict's `msg` field
    already contains the fully-rendered human-readable message `ctx`
    would have been used to build, so nothing meaningful is lost by
    removing it - only the non-serializable, redundant raw object.
    """
    sanitized = []
    for error in errors:
        cleaned = {k: v for k, v in error.items() if k != "ctx"}
        sanitized.append(cleaned)
    return sanitized


def _build_error_response(
    request: Request,
    *,
    http_status_code: int,
    code: str,
    message: str,
    stage: str | None = None,
    details: dict | None = None,
) -> JSONResponse:
    """
    Construct the single, consistent error JSON envelope used by
    every handler in this module.

    WHY `request_id` is pulled from `request.state`: a request-id
    middleware (wired in `app/api/` via `core.dependencies.get_request_id`)
    stamps every inbound request with a correlation id BEFORE it
    reaches a route handler. Surfacing that same id back in the error
    body is what lets an operator grep logs for the exact request that
    a user is reporting as failed.
    """
    request_id = getattr(request.state, "request_id", None)
    payload = {
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
            "details": details or {},
        },
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return JSONResponse(status_code=http_status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Attach every exception handler this service needs to the given
    FastAPI application instance.

    WHY handlers are registered here (imperatively, in one function)
    rather than via `@app.exception_handler` decorators scattered
    across files: keeping registration centralized means `main.py`
    has exactly one line - `register_exception_handlers(app)` - to
    know the service's entire error-handling surface is wired up.
    Adding a new handler is a one-file change (this one).
    """

    @app.exception_handler(IntelliPlantBaseException)
    async def handle_intelliplant_exception(
        request: Request, exc: IntelliPlantBaseException
    ) -> JSONResponse:
        """
        Catches EVERY custom exception defined in `core/exceptions.py`
        (OCR failures, embedding failures, Groq timeouts, no
        retrieval results, database failures, etc.) because they all
        inherit from `IntelliPlantBaseException`.

        WHY log level varies by status code: a 404 "no results found"
        is an expected, routine outcome and logging it at ERROR would
        create constant false-positive noise for on-call engineers. A
        5xx, by contrast, represents a genuine service fault and must
        be loud in the error-only log sink (see logging_config.py).
        """
        log_context = exc.to_log_context()
        bound_logger = logger.bind(
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url.path),
            **log_context,
        )
        if exc.http_status_code >= 500:
            bound_logger.error(f"Request failed: {exc.message}")
        elif exc.http_status_code >= 400:
            bound_logger.warning(f"Request rejected: {exc.message}")
        else:
            bound_logger.info(f"Request short-circuited: {exc.message}")

        return _build_error_response(
            request,
            http_status_code=exc.http_status_code,
            code=exc.error_code.value,
            message=exc.message,
            stage=exc.stage.value if exc.stage else None,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Catches FastAPI/Pydantic request validation failures - e.g. a
        POST /query body missing the required `query` field, or a
        POST /upload with a malformed `department` metadata field.

        WHY 422 rather than 400: this mirrors FastAPI's own default
        behavior for validation errors (Unprocessable Entity), keeping
        this service consistent with standard FastAPI semantics that
        API consumers already expect.

        WHY `_sanitize_validation_errors` is applied to `exc.errors()`
        before it goes anywhere near `details`: Pydantic v2 populates
        each error dict's `ctx` key with the ORIGINAL raw exception
        object that a `field_validator` raised (e.g. the `ValueError`
        from `QueryRequest._query_must_not_be_blank`), not a
        JSON-serializable representation of it. Passing that straight
        into a `JSONResponse` crashes `json.dumps` with a `TypeError`
        deep inside Starlette's response rendering - turning a clean
        422 into an unhandled 500. This was caught by this codebase's
        own end-to-end HTTP tests, not by inspection - a reminder that
        every exception handler needs to be exercised with a REAL
        validation failure, not just reasoned about.
        """
        sanitized_errors = _sanitize_validation_errors(exc.errors())
        logger.bind(
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url.path),
            validation_errors=sanitized_errors,
        ).warning("Request validation failed")

        return _build_error_response(
            request,
            http_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ErrorCode.VALIDATION_ERROR.value,
            message="Request validation failed. See details for the specific fields.",
            details={"validation_errors": sanitized_errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """
        Catches framework-level HTTP exceptions not raised by our own
        code - e.g. FastAPI's built-in 404 for a route that doesn't
        exist, or 405 Method Not Allowed. Wrapping these in the SAME
        envelope as our custom exceptions means API consumers never
        see two different error body shapes depending on whether the
        failure came from our business logic or from routing.
        """
        logger.bind(
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url.path),
            status_code=exc.status_code,
        ).warning(f"HTTP exception: {exc.detail}")

        return _build_error_response(
            request,
            http_status_code=exc.status_code,
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        The final safety net. Catches anything NOT already handled
        above - a bug, an unanticipated third-party library exception,
        etc. WHY this must exist: without it, an unhandled exception
        would crash out to a bare 500 with no structured logging and
        no consistent JSON body, breaking the guarantee every other
        handler in this file provides.

        WHY `diagnose`/traceback details are logged but NEVER returned
        in the response body: leaking stack traces or internal state
        to API callers is an information-disclosure risk, especially
        once this service is reachable by an orchestrator or external
        clients in production.
        """
        logger.bind(
            request_id=getattr(request.state, "request_id", None),
            path=str(request.url.path),
            exception_type=type(exc).__name__,
        ).exception("Unhandled exception")

        return _build_error_response(
            request,
            http_status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_SERVER_ERROR.value,
            message="An unexpected internal error occurred. The engineering "
            "team has been notified via error logs.",
        )
