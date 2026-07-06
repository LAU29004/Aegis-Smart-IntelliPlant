"""
app/config/settings.py

WHY THIS FILE EXISTS
---------------------
Every configurable value that Agent 1 needs at runtime lives here as a
strongly-typed field on a single Pydantic `Settings` model:

    - Groq LLM credentials / model / generation parameters
    - ChromaDB persistence location and collection naming
    - Sentence-Transformers embedding model + cross-encoder reranker
    - Chunking parameters (size / overlap) referenced by ingestion
    - Retrieval parameters (top_k before and after reranking)
    - Confidence score thresholds (Green / Amber / Red bands)
    - PostgreSQL connection details for SQLAlchemy
    - File upload constraints (size, allowed extensions, storage dir)
    - Tesseract OCR binary path
    - CORS + API host/port
    - Logging level and log file location

Downstream folders (ingestion/, embeddings/, retrieval/, llm/,
confidence/, database/, api/...) NEVER read `os.environ` directly.
They accept a `Settings` instance (via FastAPI's dependency injection,
using `get_settings`) in their constructors. This is what lets Agent
2/3/4 or a future orchestrator reuse these same service classes with
their own settings without any code changes here - the settings object
is just handed in.

`get_settings()` is wrapped in `functools.lru_cache` so the .env file
is parsed and validated exactly once per process, and every part of
the app shares the identical, immutable settings object.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Strongly typed application configuration.

    Values are loaded, in order of precedence, from:
        1. Real process environment variables (highest precedence -
           this is what Docker / Kubernetes / CI will set)
        2. A local `.env` file (developer convenience - see
           `.env.example` for the full list of variables)
        3. The default values declared below (safe, non-secret
           fallbacks only - no default ever contains a real secret)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # APPLICATION METADATA
    # WHY: Exposed on /health and in logs so ops can confirm which
    # build/environment they are talking to without SSHing into a box.
    # ------------------------------------------------------------------
    APP_NAME: str = Field(
        default="IntelliPlant Agent 1 - RAG Copilot",
        description="Human readable service name, shown in /health and logs.",
    )
    APP_VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: str = Field(
        default="development",
        description="One of: development, staging, production. Drives log "
        "verbosity and whether debug endpoints are exposed.",
    )
    DEBUG: bool = Field(default=False)

    # ------------------------------------------------------------------
    # API SERVER
    # WHY: FastAPI/uvicorn host+port are config, not hardcoded, so the
    # exact same image can be deployed behind different port mappings
    # in Docker Compose / Kubernetes without a rebuild.
    # ------------------------------------------------------------------
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    API_PREFIX: str = Field(
        default="/api/v1",
        description="Versioned prefix so Agent 2/3/4 or the orchestrator "
        "can route to this service unambiguously.",
    )
    CORS_ORIGINS: List[str] = Field(
        default=["*"],
        description="Explicit allow-list in production; '*' only acceptable "
        "in local development.",
    )

    # ------------------------------------------------------------------
    # GROQ LLM
    # WHY: Groq is the ONLY LLM provider this agent talks to (per spec:
    # no LangChain/LlamaIndex, manual implementation). Isolating every
    # Groq knob here means `app/llm/` never needs to know where these
    # values come from - it just receives a validated Settings object.
    # ------------------------------------------------------------------
    GROQ_API_KEY: str = Field(
        default="",
        description="Secret. Must be supplied via real environment "
        "variable / secrets manager in staging & production, never "
        "committed to source control.",
    )
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq-hosted model used for answer generation and "
        "follow-up question generation.",
    )
    GROQ_TEMPERATURE: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Deliberately low - this is a factual retrieval "
        "system, not a creative one. Low temperature reduces the chance "
        "of the LLM drifting from the supplied context.",
    )
    GROQ_MAX_TOKENS: int = Field(default=1024, ge=1, le=8192)
    GROQ_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Hard timeout for Groq calls so a slow upstream "
        "response can never hang a request indefinitely; the error "
        "handling layer converts a timeout into a clean HTTP 504.",
    )
    GROQ_MAX_RETRIES: int = Field(default=2, ge=0, le=5)

    # ------------------------------------------------------------------
    # EMBEDDINGS (Sentence-Transformers)
    # WHY: Chosen once, used everywhere - ingestion embeds chunks with
    # this exact model, retrieval embeds the query with this exact
    # model. If these ever drift apart, vector search silently returns
    # garbage. Centralizing the model name is what prevents that class
    # of bug entirely.
    # ------------------------------------------------------------------
    EMBEDDING_MODEL_NAME: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Bi-encoder used for the initial ANN vector search "
        "over ChromaDB.",
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Output dimensionality of EMBEDDING_MODEL_NAME. Used "
        "to validate the ChromaDB collection schema at startup so a "
        "model swap without a re-index fails loudly instead of silently.",
    )
    EMBEDDING_BATCH_SIZE: int = Field(default=32, ge=1, le=256)

    # ------------------------------------------------------------------
    # CROSS ENCODER RERANKER
    # WHY: The bi-encoder (above) is fast but imprecise at top-of-list
    # ranking. The cross-encoder re-scores the top-K candidates with a
    # much more accurate (but slower) joint query-document encoding.
    # Kept as a separate model config because it is a fundamentally
    # different architecture with its own load/latency profile.
    # ------------------------------------------------------------------
    CROSS_ENCODER_MODEL_NAME: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    # ------------------------------------------------------------------
    # CHUNKING
    # WHY: Fixed at 512/50 per spec. Declared here (not hardcoded inside
    # the chunker) so the SAME numbers are used by ingestion when
    # writing chunks and can be surfaced in API responses/logs for
    # debugging retrieval quality without hunting through code.
    # ------------------------------------------------------------------
    CHUNK_SIZE_TOKENS: int = Field(default=512, ge=50, le=4096)
    CHUNK_OVERLAP_TOKENS: int = Field(default=50, ge=0, le=2048)

    @field_validator("CHUNK_OVERLAP_TOKENS")
    @classmethod
    def _overlap_must_be_smaller_than_chunk(cls, v: int, info) -> int:
        """
        WHY: An overlap >= chunk size produces infinite or duplicate
        chunks during sliding-window splitting. Failing fast at
        startup is far cheaper than debugging a runaway ingestion job.
        """
        chunk_size = info.data.get("CHUNK_SIZE_TOKENS")
        if chunk_size is not None and v >= chunk_size:
            raise ValueError(
                f"CHUNK_OVERLAP_TOKENS ({v}) must be smaller than "
                f"CHUNK_SIZE_TOKENS ({chunk_size})."
            )
        return v

    # ------------------------------------------------------------------
    # RETRIEVAL
    # WHY: Two-stage retrieval per spec - broad ANN recall (TOP_K_VECTOR)
    # narrowed by precise cross-encoder reranking (TOP_K_RERANK). Both
    # are configurable so we can tune recall/precision/latency without
    # touching retrieval logic.
    # ------------------------------------------------------------------
    TOP_K_VECTOR_SEARCH: int = Field(default=15, ge=1, le=100)
    TOP_K_AFTER_RERANK: int = Field(default=5, ge=1, le=50)

    @field_validator("TOP_K_AFTER_RERANK")
    @classmethod
    def _rerank_k_cannot_exceed_vector_k(cls, v: int, info) -> int:
        """
        WHY: You cannot rerank-and-keep more documents than were
        retrieved in the first stage. Catching this at config-load
        time avoids a confusing empty-slice bug deep in retrieval.py.
        """
        vector_k = info.data.get("TOP_K_VECTOR_SEARCH")
        if vector_k is not None and v > vector_k:
            raise ValueError(
                f"TOP_K_AFTER_RERANK ({v}) cannot exceed "
                f"TOP_K_VECTOR_SEARCH ({vector_k})."
            )
        return v

    # ------------------------------------------------------------------
    # CONFIDENCE SCORING
    # WHY: The spec defines fixed Green/Amber/Red bands off similarity
    # score. Making the thresholds configurable (rather than magic
    # numbers inside confidence/) lets us recalibrate as we observe
    # real-world retrieval quality, without a code change.
    # ------------------------------------------------------------------
    CONFIDENCE_GREEN_THRESHOLD: float = Field(default=80.0, ge=0.0, le=100.0)
    CONFIDENCE_AMBER_THRESHOLD: float = Field(default=60.0, ge=0.0, le=100.0)

    @field_validator("CONFIDENCE_AMBER_THRESHOLD")
    @classmethod
    def _amber_must_be_below_green(cls, v: float, info) -> float:
        """
        WHY: The band logic (`confidence/` module) assumes
        GREEN > AMBER strictly. Validating the ordering here means
        that assumption can never be silently violated by a bad .env.
        """
        green = info.data.get("CONFIDENCE_GREEN_THRESHOLD")
        if green is not None and v >= green:
            raise ValueError(
                f"CONFIDENCE_AMBER_THRESHOLD ({v}) must be strictly less "
                f"than CONFIDENCE_GREEN_THRESHOLD ({green})."
            )
        return v

    # ------------------------------------------------------------------
    # FOLLOW-UP QUESTIONS
    # ------------------------------------------------------------------
    FOLLOWUP_QUESTION_COUNT: int = Field(default=3, ge=0, le=10)

    # ------------------------------------------------------------------
    # CHROMADB (VECTOR STORE)
    # WHY: Persisted to disk (not in-memory) so ingested documents
    # survive a service restart - critical for an industrial knowledge
    # base that may take hours to fully re-index from scratch.
    # ------------------------------------------------------------------
    CHROMA_PERSIST_DIRECTORY: str = Field(default="./data/chroma_store")
    CHROMA_COLLECTION_NAME: str = Field(default="intelliplant_documents")

    # ------------------------------------------------------------------
    # POSTGRESQL (RELATIONAL METADATA STORE)
    # WHY: ChromaDB holds vectors + light metadata for search; Postgres
    # is the system of record for documents, chunks, users, conversation
    # history, query logs and feedback - i.e. anything that needs
    # relational integrity, joins, or transactional writes.
    # ------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/intelliplant",
        description="SQLAlchemy connection string. Must use the "
        "psycopg2 driver for synchronous access in this service.",
    )
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    DB_POOL_TIMEOUT_SECONDS: int = Field(default=30, ge=1)
    DB_ECHO_SQL: bool = Field(
        default=False,
        description="Set True only for local debugging - logs every "
        "SQL statement, far too noisy for staging/production.",
    )

    # ------------------------------------------------------------------
    # FILE UPLOAD / INGESTION
    # WHY: Upper bound on upload size and a strict allow-list of
    # extensions are a basic defense-in-depth measure so the ingestion
    # pipeline (OCR, PyMuPDF) is never handed an unexpected file type
    # that could crash a worker or be used for abuse.
    # ------------------------------------------------------------------
    UPLOAD_DIRECTORY: str = Field(default="./data/uploads")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, ge=1, le=1024)
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
    )

    # ------------------------------------------------------------------
    # OCR (TESSERACT)
    # WHY: Tesseract's binary location varies across OS/containers.
    # Externalizing it means the Dockerfile can set the correct path
    # for the base image without touching ingestion code.
    # ------------------------------------------------------------------
    TESSERACT_CMD_PATH: str = Field(
        default="/usr/bin/tesseract",
        description="Absolute path to the tesseract binary inside the "
        "container/host.",
    )
    OCR_LANGUAGE: str = Field(default="eng")
    OCR_DPI: int = Field(
        default=300,
        description="Rasterization DPI when rendering scanned PDF pages "
        "to images before OCR. 300 is the standard sweet spot between "
        "OCR accuracy and processing time.",
    )

    # ------------------------------------------------------------------
    # LOGGING
    # WHY: Centralized so every module's Loguru logger is configured
    # identically (same format, same sinks, same rotation policy) -
    # see app/config/logging_config.py.
    # ------------------------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO")
    LOG_DIRECTORY: str = Field(default="./logs")
    LOG_ROTATION: str = Field(
        default="50 MB",
        description="Loguru rotation policy - roll to a new file once "
        "the active log file reaches this size.",
    )
    LOG_RETENTION: str = Field(
        default="30 days",
        description="How long rotated log files are kept before Loguru "
        "deletes them automatically.",
    )
    LOG_JSON_FORMAT: bool = Field(
        default=False,
        description="When True, logs are emitted as structured JSON "
        "lines - useful in production for ingestion by log aggregators "
        "(e.g. ELK, CloudWatch). Human-readable text in development.",
    )

    # ------------------------------------------------------------------
    # CONVERSATION MEMORY
    # WHY: Bounds how much prior conversation is replayed into the LLM
    # prompt, both to control token cost and to stop stale context
    # from polluting a fresh line of questioning.
    # ------------------------------------------------------------------
    CONVERSATION_HISTORY_MAX_TURNS: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def _ensure_runtime_directories_exist(self) -> "Settings":
        """
        WHY: Fail fast at startup rather than on the first upload/log
        write. Creating these directories here (idempotently) means
        every downstream module can assume they already exist.
        """
        for directory in (
            self.CHROMA_PERSIST_DIRECTORY,
            self.UPLOAD_DIRECTORY,
            self.LOG_DIRECTORY,
        ):
            Path(directory).mkdir(parents=True, exist_ok=True)
        return self

    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment_name(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        normalized = v.lower().strip()
        if normalized not in allowed:
            raise ValueError(
                f"ENVIRONMENT must be one of {sorted(allowed)}, got '{v}'."
            )
        return normalized

    @property
    def is_production(self) -> bool:
        """WHY: Convenience flag so services can toggle strictness "
        (e.g. disable verbose error bodies) without repeating the
        string comparison everywhere."""
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Return the process-wide singleton `Settings` instance.

    WHY `lru_cache` here specifically:
        - `.env` parsing + validation happens exactly once per process,
          not on every request.
        - FastAPI's dependency injection (`Depends(get_settings)`)
          therefore hands every request handler the SAME object,
          which is what makes it safe to also use `get_settings()`
          directly inside service constructors that are built once at
          application startup (see app/services/*).
        - Tests can bypass the cache entirely by constructing
          `Settings(**overrides)` directly instead of calling this
          function, so the singleton never leaks between test cases.
    """
    return Settings()
