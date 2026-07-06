"""
app/core/constants.py

WHY THIS FILE EXISTS
---------------------
The spec requires every stage of two pipelines (query pipeline and
ingestion pipeline) to be logged, and requires confidence bands and
document types to behave identically everywhere they are referenced.
Without a single enum for these, it is extremely easy for one module
to log the stage as the string "embedding" and another as "Embedding"
or "EMBED" - which silently breaks log-based monitoring/alerting and
any downstream analytics on query_logs.

Using `str, Enum` (rather than a plain `Enum`) means these values
serialize cleanly to JSON and Postgres string columns without a
custom encoder, while still giving IDEs/type-checkers autocomplete
and preventing typos at the call site.
"""

from enum import Enum


class PipelineStage(str, Enum):
    """
    Every distinct stage across BOTH pipelines defined in the spec:

        Query pipeline:
            User Query -> Embedding -> Vector Search -> Metadata
            Filtering -> Cross Encoder ReRanking -> Context Builder ->
            Groq LLM -> Citation Builder -> Confidence Score ->
            Follow-up Question Generator -> JSON Response

        Ingestion pipeline:
            Upload -> OCR if required -> Text Extraction -> Cleaning ->
            Chunking -> Metadata Extraction -> Embedding -> Store in
            ChromaDB -> Store Metadata in PostgreSQL

    WHY logged and raised exceptions both carry a `PipelineStage`:
    it lets ops filter logs/errors by exactly where in either pipeline
    something happened, without parsing free-text messages.
    """

    # --- Ingestion pipeline ---
    UPLOAD = "upload"
    OCR = "ocr"
    TEXT_EXTRACTION = "text_extraction"
    CLEANING = "cleaning"
    CHUNKING = "chunking"
    METADATA_EXTRACTION = "metadata_extraction"
    DOCUMENT_EMBEDDING = "document_embedding"
    VECTOR_STORE_WRITE = "vector_store_write"
    METADATA_STORE_WRITE = "metadata_store_write"

    # --- Query pipeline ---
    QUERY_EMBEDDING = "query_embedding"
    VECTOR_SEARCH = "vector_search"
    METADATA_FILTERING = "metadata_filtering"
    RERANKING = "reranking"
    CONTEXT_BUILDING = "context_building"
    PROMPT_BUILDING = "prompt_building"
    LLM_GENERATION = "llm_generation"
    CITATION_BUILDING = "citation_building"
    CONFIDENCE_SCORING = "confidence_scoring"
    FOLLOWUP_GENERATION = "followup_generation"
    RESPONSE_ASSEMBLY = "response_assembly"


class ConfidenceBand(str, Enum):
    """
    The three confidence bands mandated by the spec:
        Above 80    -> GREEN
        60-80       -> AMBER
        Below 60    -> RED

    WHY an enum instead of raw strings "Green"/"Amber"/"Red" scattered
    through confidence/ and schemas/: guarantees the API response
    field `confidence.band` can only ever be one of these three exact
    values, which the frontend/orchestrator can then safely switch on.
    """

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class DocumentType(str, Enum):
    """
    Supported (and near-future) document types per the spec's
    Document Ingestion section.

    WHY `EXCEL` is included now even though support is "future":
    declaring it here lets the Documents table / API schemas reference
    a stable enum value today, so adding real Excel ingestion later is
    an additive change to `ingestion/`, not a breaking schema change.
    """

    PDF = "pdf"
    SCANNED_PDF = "scanned_pdf"
    IMAGE = "image"
    EXCEL = "excel"  # future support, per spec


class ErrorCode(str, Enum):
    """
    Machine-readable error codes returned in the `error.code` field of
    every error JSON response (see exception_handlers.py).

    WHY separate from the HTTP status code: HTTP status alone can't
    distinguish "Groq timed out" from "Groq rate limited us" (both
    could plausibly map to different or even the same status), and a
    calling agent/orchestrator needs to branch on the SPECIFIC failure
    reason (e.g. retry on GROQ_TIMEOUT, but not on GROQ_AUTH_FAILED).
    """

    VALIDATION_ERROR = "VALIDATION_ERROR"
    DOCUMENT_VALIDATION_ERROR = "DOCUMENT_VALIDATION_ERROR"
    OCR_FAILED = "OCR_FAILED"
    TEXT_EXTRACTION_FAILED = "TEXT_EXTRACTION_FAILED"
    CHUNKING_FAILED = "CHUNKING_FAILED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    VECTOR_STORE_CONNECTION_ERROR = "VECTOR_STORE_CONNECTION_ERROR"
    VECTOR_STORE_WRITE_ERROR = "VECTOR_STORE_WRITE_ERROR"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    NO_RETRIEVAL_RESULTS = "NO_RETRIEVAL_RESULTS"
    RERANKING_FAILED = "RERANKING_FAILED"
    PROMPT_BUILD_FAILED = "PROMPT_BUILD_FAILED"
    GROQ_API_ERROR = "GROQ_API_ERROR"
    GROQ_TIMEOUT = "GROQ_TIMEOUT"
    GROQ_RATE_LIMITED = "GROQ_RATE_LIMITED"
    GROQ_AUTH_FAILED = "GROQ_AUTH_FAILED"
    CITATION_BUILD_FAILED = "CITATION_BUILD_FAILED"
    CONFIDENCE_SCORING_FAILED = "CONFIDENCE_SCORING_FAILED"
    FOLLOWUP_GENERATION_FAILED = "FOLLOWUP_GENERATION_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DUPLICATE_RECORD = "DUPLICATE_RECORD"
    CONVERSATION_MEMORY_ERROR = "CONVERSATION_MEMORY_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


# WHY defined as a module-level constant rather than inline in
# prompts/ or llm/: the spec mandates this EXACT string when no
# relevant context is found, and it is also referenced by
# `NoRetrievalResultsError` below (core/exceptions.py) and by the
# prompt builder (future prompts/ folder) - both must stay byte-for-
# byte identical, which a shared constant guarantees.
NO_CONTEXT_FOUND_MESSAGE = "No relevant information found in indexed documents."
