"""
app/database/enums.py

WHY THIS FILE EXISTS
---------------------
Distinct from `app/core/constants.py`, which holds PIPELINE-level
enums (PipelineStage, ConfidenceBand, DocumentType, ErrorCode) used
across logging/exceptions/API responses. The enums here are
PERSISTENCE-level: they exist specifically to constrain what values a
database COLUMN may hold, enforced both at the Python/ORM layer and
(via SQLAlchemy `Enum`) as a real CHECK constraint / native enum type
at the database layer.

Some enums genuinely belong in both worlds (e.g. `DocumentType` and
`ConfidenceBand` are reused directly from `core.constants` inside the
models below, rather than redefined here) - see model files for that
reuse. This file only defines enums that are specific to database
row lifecycle/roles and have no meaning outside persistence.
"""

from enum import Enum


class DocumentStatus(str, Enum):
    """
    Lifecycle status of a row in the `documents` table, tracking its
    progress through the ingestion pipeline (Upload -> OCR -> Text
    Extraction -> Cleaning -> Chunking -> Metadata Extraction ->
    Embedding -> Store in ChromaDB -> Store Metadata in PostgreSQL).

    WHY this exists as a persisted status rather than only being
    inferred from logs: the GET /documents endpoint (upcoming `api/`
    folder) needs to answer "is this document ready to be queried
    yet?" with a single indexed column lookup, not by replaying logs.
    """

    PENDING = "pending"  # row created, ingestion not yet started
    PROCESSING = "processing"  # actively moving through the pipeline
    COMPLETED = "completed"  # fully chunked, embedded, and searchable
    FAILED = "failed"  # ingestion failed at some stage; see error_message


class UserRole(str, Enum):
    """
    Coarse-grained role for access control. WHY only three roles: the
    spec does not define a detailed permission matrix, so this starts
    minimal (viewer/engineer/admin) rather than over-engineering a
    permissions system speculatively. Extending this is additive.
    """

    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class ConversationRole(str, Enum):
    """
    Distinguishes a user's turn from the assistant's turn within a
    conversation history row, mirroring the standard chat-message
    role convention (user/assistant) used by most LLM APIs, including
    Groq's - which keeps conversation replaying (upcoming `services/`
    conversation memory) a direct mapping with no translation layer.
    """

    USER = "user"
    ASSISTANT = "assistant"


class FeedbackRating(str, Enum):
    """
    Simple thumbs-up/thumbs-down rating for a query response.

    WHY not a 1-5 star scale: the spec's JSON response is a
    single-answer RAG response (not a multi-option recommendation),
    where the only meaningful question to ask an engineer on the
    plant floor is "was this answer correct/useful or not" - a binary
    signal is faster to give and more reliable to aggregate than a
    5-point scale for this use case.
    """

    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
