"""
app/core/exceptions.py

WHY THIS FILE EXISTS
---------------------
The spec explicitly requires handling of: OCR failures, embedding
failures, Groq timeout, no retrieval results, and database failures.
Rather than letting raw library exceptions (pytesseract.TesseractError,
httpx.TimeoutException, sqlalchemy.exc.OperationalError, ...) leak out
of their modules and force `api/` to `except Exception` blindly, EVERY
module in this codebase raises one of the typed exceptions below.

This buys us three things:
    1. `api/` (and `exception_handlers.py`) can catch ONE base class
       (`IntelliPlantBaseException`) and still know the exact stage,
       HTTP status, and machine-readable error code to return, because
       each subclass carries that information itself.
    2. Every exception is loggable and serializable identically (see
       `to_log_context` / `to_error_payload`), so `services/` never
       has to know HOW an error will be presented - it just raises
       the right typed exception and walks away.
    3. Future agents (2/3/4) that reuse these service classes (e.g. a
       shared `EmbeddingService`) inherit a battle-tested, consistent
       error contract for free instead of re-inventing one.
"""

from typing import Any, Dict, Optional

from app.core.constants import ErrorCode, PipelineStage


class IntelliPlantBaseException(Exception):
    """
    Root of the entire exception hierarchy for this service.

    WHY every custom exception inherits from this ONE class (and not
    directly from `Exception`): `exception_handlers.py` registers a
    single FastAPI handler for `IntelliPlantBaseException` and, by
    virtue of subclassing, that one handler automatically catches
    every specific error type below with zero additional registration
    per-exception. Adding a brand new exception subclass therefore
    requires touching exactly one file (this one) - the handler layer
    never needs to change.

    Attributes:
        message: Human-readable explanation, safe to show to a caller
            (never include secrets, stack traces, or SQL in this).
        error_code: Machine-readable `ErrorCode` enum value so a
            calling agent/orchestrator can branch on the exact failure
            without parsing free text.
        stage: The `PipelineStage` this error occurred in, used for
            structured logging and for populating query_logs/errors
            in the database.
        http_status_code: The HTTP status this should map to when
            surfaced through the API layer.
        details: Optional structured extra context (e.g. document_id,
            chunk_id, retry_count) useful for debugging but never
            containing secrets.
        original_exception: The lower-level exception that triggered
            this one, if any (e.g. the underlying `httpx.TimeoutException`
            for a `GroqTimeoutError`). Preserved for logging/tracebacks
            only - never serialized into the API response.
    """

    error_code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR
    http_status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        stage: Optional[PipelineStage] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.details = details or {}
        self.original_exception = original_exception

    def to_log_context(self) -> Dict[str, Any]:
        """
        WHY: `exception_handlers.py` and any module that catches and
        re-logs one of these exceptions needs a consistent dict to
        pass into Loguru's `.bind(...)` / structured logging, rather
        than hand-rolling f-strings at every call site.
        """
        return {
            "error_code": self.error_code.value,
            "stage": self.stage.value if self.stage else None,
            "http_status_code": self.http_status_code,
            "details": self.details,
            "original_exception": repr(self.original_exception)
            if self.original_exception
            else None,
        }

    def to_error_payload(self) -> Dict[str, Any]:
        """
        WHY: The exact JSON shape returned to API callers. Kept
        separate from `to_log_context` because the log context
        includes `original_exception` (useful internally, never sent
        to a client) while this payload is safe for external exposure.
        """
        return {
            "code": self.error_code.value,
            "message": self.message,
            "stage": self.stage.value if self.stage else None,
            "details": self.details,
        }


# =============================================================================
# DOCUMENT VALIDATION / UPLOAD
# =============================================================================


class DocumentValidationError(IntelliPlantBaseException):
    """
    Raised when an uploaded file fails validation: disallowed
    extension, exceeds MAX_UPLOAD_SIZE_MB, corrupted/unreadable file,
    or missing required metadata (department, equipment_id, etc.).

    WHY 400 and not 422: this represents a malformed CLIENT request
    (wrong file type/size) rather than a semantically valid request
    that the server failed to process.
    """

    error_code = ErrorCode.DOCUMENT_VALIDATION_ERROR
    http_status_code = 400


# =============================================================================
# INGESTION PIPELINE
# =============================================================================


class OCRProcessingError(IntelliPlantBaseException):
    """
    Raised when Tesseract OCR fails on a scanned PDF page or image -
    e.g. the binary is missing/misconfigured (TESSERACT_CMD_PATH),
    the image is unreadable, or OCR produces empty output for a page
    that visibly contains text.

    WHY 422: the upload itself was valid, but the server could not
    successfully process its *content*.
    """

    error_code = ErrorCode.OCR_FAILED
    http_status_code = 422


class TextExtractionError(IntelliPlantBaseException):
    """
    Raised when PyMuPDF fails to open or extract text from a PDF
    (e.g. corrupted PDF structure, encrypted PDF without a password).
    """

    error_code = ErrorCode.TEXT_EXTRACTION_FAILED
    http_status_code = 422


class ChunkingError(IntelliPlantBaseException):
    """
    Raised when the 512/50 sliding-window chunker cannot produce valid
    chunks - e.g. cleaned text is empty, or the token count for a
    single un-splittable unit exceeds CHUNK_SIZE_TOKENS in a way the
    chunker cannot safely resolve.
    """

    error_code = ErrorCode.CHUNKING_FAILED
    http_status_code = 500


# =============================================================================
# EMBEDDINGS
# =============================================================================


class EmbeddingGenerationError(IntelliPlantBaseException):
    """
    Raised when sentence-transformers fails to embed text - e.g. the
    model failed to load, out-of-memory during batch encoding, or the
    input text is empty/invalid after cleaning.

    WHY 503: this represents a downstream (embedding model) capacity
    or availability problem, not a client input error, so we mark it
    as Service Unavailable and let the caller/orchestrator decide
    whether to retry.
    """

    error_code = ErrorCode.EMBEDDING_FAILED
    http_status_code = 503


# =============================================================================
# VECTOR STORE (CHROMADB)
# =============================================================================


class VectorStoreError(IntelliPlantBaseException):
    """Base class for any ChromaDB-related failure."""

    error_code = ErrorCode.VECTOR_STORE_ERROR
    http_status_code = 503


class VectorStoreConnectionError(VectorStoreError):
    """
    Raised when the ChromaDB client cannot connect to / open the
    persistent collection at CHROMA_PERSIST_DIRECTORY.
    """

    error_code = ErrorCode.VECTOR_STORE_CONNECTION_ERROR
    http_status_code = 503


class VectorStoreWriteError(VectorStoreError):
    """
    Raised when writing embedded chunks + metadata into ChromaDB
    fails mid-ingestion (e.g. dimension mismatch against the
    collection's configured EMBEDDING_DIMENSION, disk full).
    """

    error_code = ErrorCode.VECTOR_STORE_WRITE_ERROR
    http_status_code = 503


# =============================================================================
# RETRIEVAL / RERANKING
# =============================================================================


class RetrievalError(IntelliPlantBaseException):
    """
    Raised for unexpected failures during vector search or metadata
    filtering (distinct from the *expected*, non-error case of zero
    matches, which is `NoRetrievalResultsError` below).
    """

    error_code = ErrorCode.RETRIEVAL_FAILED
    http_status_code = 500


class NoRetrievalResultsError(IntelliPlantBaseException):
    """
    Raised when vector search + metadata filtering legitimately return
    zero usable chunks for a query.

    WHY this is modeled as an exception rather than just returning an
    empty list: it lets the query pipeline short-circuit cleanly at
    the retrieval stage and route straight to the spec-mandated
    response - "No relevant information found in indexed documents." -
    without every downstream stage (reranking, context building,
    prompt building, LLM call) needing its own empty-input guard
    clause. One `except NoRetrievalResultsError` in the orchestrating
    service handles it.

    WHY 404 and not 200-with-empty-answer: from an HTTP semantics
    standpoint, "no matching resource was found for this query" is a
    404. The API layer is responsible for converting this into the
    spec's exact JSON response shape (still including citations=[],
    confidence=RED, etc.) rather than an error-only body - see
    `api/` folder (upcoming) for that translation.
    """

    error_code = ErrorCode.NO_RETRIEVAL_RESULTS
    http_status_code = 404

    def __init__(
        self,
        message: str = "No relevant information found in indexed documents.",
        *,
        stage: Optional[PipelineStage] = PipelineStage.VECTOR_SEARCH,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            stage=stage,
            details=details,
            original_exception=original_exception,
        )


class RerankingError(IntelliPlantBaseException):
    """
    Raised when the cross-encoder reranker fails - e.g. model load
    failure, or a shape mismatch between query/candidate pairs.
    """

    error_code = ErrorCode.RERANKING_FAILED
    http_status_code = 500


# =============================================================================
# PROMPT BUILDING
# =============================================================================


class PromptBuildError(IntelliPlantBaseException):
    """
    Raised when the context builder / prompt builder cannot assemble
    a valid prompt - e.g. the reranked chunks, once concatenated,
    exceed the model's context window even after truncation logic.
    """

    error_code = ErrorCode.PROMPT_BUILD_FAILED
    http_status_code = 500


# =============================================================================
# GROQ LLM
# =============================================================================


class GroqAPIError(IntelliPlantBaseException):
    """
    Base class for any non-timeout, non-auth, non-rate-limit failure
    returned by the Groq API (e.g. a 5xx from Groq itself, or a
    malformed response body).

    WHY 502: Agent 1 acting as a proxy to an upstream (Groq) that
    itself failed is the textbook definition of a Bad Gateway.
    """

    error_code = ErrorCode.GROQ_API_ERROR
    http_status_code = 502


class GroqTimeoutError(GroqAPIError):
    """
    Raised when a Groq call exceeds GROQ_TIMEOUT_SECONDS.

    WHY 504: distinguishes "Groq did not respond in time" (Gateway
    Timeout) from "Groq responded with an error" (502), which matters
    to a calling orchestrator deciding whether a retry is likely to
    succeed.
    """

    error_code = ErrorCode.GROQ_TIMEOUT
    http_status_code = 504


class GroqRateLimitError(GroqAPIError):
    """Raised when Groq returns a 429 rate-limit response."""

    error_code = ErrorCode.GROQ_RATE_LIMITED
    http_status_code = 429


class GroqAuthenticationError(GroqAPIError):
    """
    Raised when Groq rejects GROQ_API_KEY (invalid/expired/revoked).

    WHY this is NOT retried automatically by the LLM client (see
    upcoming `llm/` folder): retrying an auth failure without human
    intervention just wastes the retry budget - this is surfaced
    immediately instead.
    """

    error_code = ErrorCode.GROQ_AUTH_FAILED
    http_status_code = 401


# =============================================================================
# CITATIONS / CONFIDENCE / FOLLOW-UPS
# =============================================================================


class CitationBuildError(IntelliPlantBaseException):
    """
    Raised when the citation builder cannot map the LLM's answer back
    to the source chunks it was generated from (e.g. malformed chunk
    metadata missing document_name/page_number).
    """

    error_code = ErrorCode.CITATION_BUILD_FAILED
    http_status_code = 500


class ConfidenceScoringError(IntelliPlantBaseException):
    """
    Raised when confidence cannot be computed from the reranked
    similarity scores (e.g. no scores present, non-numeric score).
    """

    error_code = ErrorCode.CONFIDENCE_SCORING_FAILED
    http_status_code = 500


class FollowUpGenerationError(IntelliPlantBaseException):
    """
    Raised when follow-up question generation fails.

    WHY this exists as its OWN exception rather than reusing
    `GroqAPIError`: follow-up generation is explicitly a
    non-critical, best-effort pipeline stage. The query service
    (upcoming `services/` folder) is expected to catch this
    specifically and degrade gracefully - returning `followups: []`
    with the main answer still intact - rather than failing the
    entire request the way a `GroqAPIError` during the main answer
    generation would.
    """

    error_code = ErrorCode.FOLLOWUP_GENERATION_FAILED
    http_status_code = 500


# =============================================================================
# DATABASE (POSTGRESQL)
# =============================================================================


class DatabaseError(IntelliPlantBaseException):
    """Base class for any SQLAlchemy/PostgreSQL failure."""

    error_code = ErrorCode.DATABASE_ERROR
    http_status_code = 500


class DatabaseConnectionError(DatabaseError):
    """
    Raised when the connection pool cannot reach PostgreSQL at
    DATABASE_URL (e.g. DB down, network partition, pool exhausted
    beyond DB_POOL_TIMEOUT_SECONDS).
    """

    error_code = ErrorCode.DATABASE_CONNECTION_ERROR
    http_status_code = 503


class RecordNotFoundError(DatabaseError):
    """
    Raised when a lookup by primary key / unique field (document,
    chunk, user, conversation) finds no matching row.
    """

    error_code = ErrorCode.RECORD_NOT_FOUND
    http_status_code = 404


class DuplicateRecordError(DatabaseError):
    """
    Raised when an insert violates a uniqueness constraint (e.g.
    re-uploading a document whose content hash already exists).
    """

    error_code = ErrorCode.DUPLICATE_RECORD
    http_status_code = 409


# =============================================================================
# CONVERSATION MEMORY
# =============================================================================


class ConversationMemoryError(IntelliPlantBaseException):
    """
    Raised when conversation history cannot be loaded or persisted
    (e.g. corrupted history payload, serialization failure of a prior
    turn). Kept distinct from generic `DatabaseError` because
    conversation memory is a reusable service other agents will also
    depend on (per the spec's orchestration requirements), so its
    failure mode deserves its own identity in logs/metrics.
    """

    error_code = ErrorCode.CONVERSATION_MEMORY_ERROR
    http_status_code = 500
