"""
app/database/models/feedback.py

WHY THIS FILE EXISTS
---------------------
Captures explicit human judgment on a specific answer (thumbs up /
thumbs down + optional comment), tied back to the exact `QueryLog`
row that produced it. This is the ground-truth signal that would
eventually feed retrieval-quality tuning (e.g. noticing a cluster of
thumbs-down on RED-confidence answers validates the confidence
threshold calibration) - without this table, confidence scoring would
be flying blind on whether its bands actually correlate with answer
quality as judged by real users.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import FeedbackRating

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from app.database.models.query_log import QueryLog
    from app.database.models.user import User


class Feedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single piece of user feedback on one query's answer.

    WHY `query_log_id` uses `ondelete="CASCADE"`: feedback has no
    meaning independent of the query it's about - if a query log row
    is ever purged (e.g. a data-retention policy removing query logs
    older than N days), its feedback should be purged with it rather
    than becoming an orphaned row referencing nothing.

    WHY `user_id` is nullable (unlike `query_log_id`): feedback may be
    given anonymously or by a user account that has since been
    deactivated/deleted - the feedback signal itself (was this answer
    good?) remains valuable for quality analysis even without knowing
    exactly who gave it, so we don't want a user deletion to cascade
    and destroy that signal.
    """

    __tablename__ = "feedback"

    query_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("query_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[FeedbackRating] = mapped_column(
        Enum(FeedbackRating, name="feedback_rating", native_enum=False, length=20),
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Optional free-text elaboration, e.g. 'citation pointed to the "
        "wrong page' - useful qualitative signal alongside the binary rating.",
    )

    # --- Relationships ---------------------------------------------
    query_log: Mapped["QueryLog"] = relationship(back_populates="feedback_entries")
    user: Mapped[Optional["User"]] = relationship(back_populates="feedback_entries")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Feedback id={self.id} query_log_id={self.query_log_id} rating={self.rating.value}>"
