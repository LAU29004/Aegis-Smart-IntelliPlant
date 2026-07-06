"""
app/database/models/query_log.py

WHY THIS FILE EXISTS
---------------------
Every call to POST /query gets exactly one row here, persisted AFTER
the full pipeline (Embedding -> Vector Search -> Metadata Filtering ->
Reranking -> Context Building -> Groq LLM -> Citation Builder ->
Confidence Score -> Follow-up Generation -> JSON Response) completes -
successfully or not. This is what backs GET /history, and is the raw
data any future analytics on retrieval quality, confidence
distribution, or per-department usage would be built from.
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.constants import ConfidenceBand
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from app.database.models.feedback import Feedback
    from app.database.models.user import User


class QueryLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single record of one query pipeline execution: the question
    asked, the answer produced, its confidence, which chunks were
    used, and how long each major stage took.

    WHY `confidence_band` is stored as its OWN column (redundant with
    what could be derived from `confidence_score` at read time): GET
    /history and any dashboard built on top of it need to filter/group
    by band cheaply (e.g. "show me all RED-confidence queries this
    week" as an indexed WHERE clause) without recomputing the
    Green/Amber/Red threshold logic in every consumer.

    WHY `retrieved_chunk_ids` is a JSON array rather than a proper
    many-to-many association table: the relationship between a query
    and the chunks it retrieved is write-once, read-rarely, and purely
    for audit/debugging ("which chunks fed this specific answer") -
    it does not need referential integrity (a chunk could later be
    deleted while its historical query log should still show which id
    it once was), so a lightweight JSON column is the right tool here,
    not a fully normalized join table.
    """

    __tablename__ = "query_logs"

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Correlates this row with the request-id assigned by "
        "app.core.dependencies.RequestIDMiddleware, tying this database "
        "record directly back to the exact log lines for that request.",
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Groups this query with its conversation turns in "
        "ConversationHistory, when the query was part of a multi-turn "
        "conversation rather than a one-off lookup.",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Null when the pipeline short-circuited at retrieval with "
        "NoRetrievalResultsError, or when LLM generation itself failed.",
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="0-100 score derived from reranked similarity, per the spec's "
        "confidence engine. Null if no chunks were retrieved.",
    )
    confidence_band: Mapped[Optional[ConfidenceBand]] = mapped_column(
        Enum(ConfidenceBand, name="confidence_band", native_enum=False, length=10),
        nullable=True,
    )
    retrieved_chunk_ids: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="List of Chunk UUIDs (as strings) that were passed into the "
        "final LLM context for this query, in reranked order - the raw "
        "material the Citation Builder used to construct `citations`.",
    )
    processing_time_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Total end-to-end pipeline latency, matching the "
        "`processing_time` field returned in the JSON response - measured "
        "via app.core.dependencies.Stopwatch.",
    )
    was_successful: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        doc="False when the pipeline raised any exception (Groq timeout, "
        "no retrieval results, etc.) - lets GET /history and dashboards "
        "distinguish real failures from legitimate empty-context answers.",
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="The ErrorCode value (see app.core.constants.ErrorCode) if "
        "was_successful is False, for failure-rate analytics by cause.",
    )

    # --- Relationships ---------------------------------------------
    user: Mapped[Optional["User"]] = relationship(back_populates="query_logs")
    feedback_entries: Mapped[List["Feedback"]] = relationship(
        back_populates="query_log",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        band = self.confidence_band.value if self.confidence_band else "n/a"
        return f"<QueryLog id={self.id} confidence_band={band} success={self.was_successful}>"
