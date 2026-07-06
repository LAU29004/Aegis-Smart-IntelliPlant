"""
Core package.

WHY a dedicated `core` package:
    This is where cross-cutting concerns that EVERY other layer
    depends on live - custom exceptions, their FastAPI handlers,
    pipeline-wide constants, lightweight DI helpers, and the abstract
    `BaseService` contract that all business-logic services implement.

    Nothing in `core` depends on `database/`, `ingestion/`,
    `embeddings/`, `retrieval/`, `llm/`, etc. The dependency direction
    is strictly one-way: those folders import FROM `core`, never the
    reverse. This is what keeps the exception hierarchy and service
    contracts reusable by Agent 2/3/4 without dragging in Agent 1's
    RAG-specific implementation details.
"""

from app.core.exceptions import (
    IntelliPlantBaseException,
    DocumentValidationError,
    OCRProcessingError,
    TextExtractionError,
    ChunkingError,
    EmbeddingGenerationError,
    VectorStoreError,
    VectorStoreConnectionError,
    VectorStoreWriteError,
    RetrievalError,
    NoRetrievalResultsError,
    RerankingError,
    PromptBuildError,
    GroqAPIError,
    GroqTimeoutError,
    GroqRateLimitError,
    GroqAuthenticationError,
    CitationBuildError,
    ConfidenceScoringError,
    FollowUpGenerationError,
    DatabaseError,
    DatabaseConnectionError,
    RecordNotFoundError,
    DuplicateRecordError,
    ConversationMemoryError,
)
from app.core.exception_handlers import register_exception_handlers
from app.core.constants import PipelineStage, ConfidenceBand, DocumentType, ErrorCode
from app.core.dependencies import get_request_id, Stopwatch
from app.core.base_service import BaseService

__all__ = [
    "IntelliPlantBaseException",
    "DocumentValidationError",
    "OCRProcessingError",
    "TextExtractionError",
    "ChunkingError",
    "EmbeddingGenerationError",
    "VectorStoreError",
    "VectorStoreConnectionError",
    "VectorStoreWriteError",
    "RetrievalError",
    "NoRetrievalResultsError",
    "RerankingError",
    "PromptBuildError",
    "GroqAPIError",
    "GroqTimeoutError",
    "GroqRateLimitError",
    "GroqAuthenticationError",
    "CitationBuildError",
    "ConfidenceScoringError",
    "FollowUpGenerationError",
    "DatabaseError",
    "DatabaseConnectionError",
    "RecordNotFoundError",
    "DuplicateRecordError",
    "ConversationMemoryError",
    "register_exception_handlers",
    "PipelineStage",
    "ConfidenceBand",
    "DocumentType",
    "ErrorCode",
    "get_request_id",
    "Stopwatch",
    "BaseService",
]
