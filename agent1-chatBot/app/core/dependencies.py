"""
app/core/dependencies.py

WHY THIS FILE EXISTS
---------------------
Two small, genuinely cross-cutting concerns that almost every request
needs, and that don't belong inside any single business-logic module:

    1. Request correlation IDs - so a single query can be traced
       across logs from retrieval/, llm/, citations/, confidence/,
       and the final API response, and so `exception_handlers.py` can
       echo the same id back to the caller for support/debugging.

    2. `Stopwatch` - a tiny timing context manager used to populate
       the spec-mandated `processing_time` field in the JSON response,
       and to log per-stage latency (Retrieval, Prompt, LLM, Response
       Time - all explicitly called out in the Logging section).

WHY these live in `core/` and not `utils/`: `utils/` (upcoming folder)
is for generic, stateless helper functions with no framework
dependency. `get_request_id` is a genuine FastAPI `Depends()` provider
wired into the request lifecycle - it belongs with the rest of the
service's dependency-injection surface in `core/`.
"""

import time
import uuid
from types import TracebackType
from typing import Optional, Type

from fastapi import Request


def get_request_id(request: Request) -> str:
    """
    FastAPI dependency that returns the current request's correlation
    ID.

    WHY it reads from `request.state.request_id` instead of minting a
    fresh UUID here: the ID must be assigned ONCE, as early as
    possible (by `RequestIDMiddleware`, wired in the upcoming `api/`
    folder) so that even validation errors and 404s - which occur
    before any route handler runs - can still be tagged with it. This
    function is simply the typed, injectable accessor for route
    handlers and services that need to log or persist that same ID
    (e.g. into the query_logs table).

    Falls back to minting a fresh ID only as a defensive measure, in
    case this dependency is ever used somewhere the middleware hasn't
    run (e.g. a unit test that builds a bare `Request`).
    """
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing
    return str(uuid.uuid4())


class RequestIDMiddleware:
    """
    ASGI middleware that stamps every inbound request with a unique
    correlation ID before anything else touches it.

    WHY implemented as raw ASGI middleware rather than FastAPI
    `BaseHTTPMiddleware`: `BaseHTTPMiddleware` buffers the entire
    response and has known streaming-response quirks. Since ingestion
    responses may eventually stream progress, raw ASGI middleware
    avoids that limitation entirely while adding negligible overhead
    for a task this small.

    Wired into the app in `app/main.py` (upcoming `api/` folder) via:
        app.add_middleware(RequestIDMiddleware)
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        # Stash it on scope.state so `Request(scope).state.request_id`
        # (used by `get_request_id` and every exception handler) sees it.
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id

        async def send_with_request_id_header(message):
            # WHY: exposing the request id in a response header lets
            # API clients (including a future orchestrator) capture it
            # even on successful (2xx) responses, not just errors -
            # useful for end-to-end tracing across all four agents.
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode("utf-8")))
            await send(message)

        await self.app(scope, receive, send_with_request_id_header)


class Stopwatch:
    """
    Simple, dependency-free timing context manager.

    WHY this exists instead of scattering `time.perf_counter()` pairs
    throughout the pipeline: every stage that must log its latency
    (per the spec's Logging section) and the overall query pipeline
    that must populate `processing_time` in the JSON response use the
    EXACT same measurement mechanism (`time.perf_counter`, which is
    monotonic and unaffected by system clock adjustments - critical
    for accurate latency measurement).

    Usage:
        with Stopwatch() as sw:
            do_expensive_thing()
        logger.info(f"Took {sw.elapsed_seconds:.3f}s")

    Or, for a single stage inline in the pipeline:
        with Stopwatch() as retrieval_timer:
            results = retrieval_service.search(query)
        total_processing_time += retrieval_timer.elapsed_seconds
    """

    def __init__(self) -> None:
        self._start: Optional[float] = None
        self._end: Optional[float] = None

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self._end = time.perf_counter()
        # WHY we deliberately do NOT suppress exceptions here (no
        # `return True`): a Stopwatch should never mask a real error
        # in the block it's timing - it only measures, it never
        # changes control flow.

    @property
    def elapsed_seconds(self) -> float:
        """
        WHY this handles the "still running" case gracefully: allows
        callers to read elapsed time for logging progress WHILE still
        inside the `with` block (e.g. a slow OCR job logging a
        heartbeat), not just after it exits.
        """
        if self._start is None:
            return 0.0
        end = self._end if self._end is not None else time.perf_counter()
        return end - self._start

    @property
    def elapsed_ms(self) -> float:
        """Convenience accessor - most log lines read better in ms."""
        return self.elapsed_seconds * 1000.0
