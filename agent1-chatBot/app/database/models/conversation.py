"""
app/database/models/conversation.py

WHY THIS FILE EXISTS
---------------------
The spec's Most Important Requirement calls out "Conversation Memory"
as a reusable service future agents must be able to depend on. This
table is the durable storage backing that service: each row is ONE
turn (either the user's message or the assistant's reply) within a
`session_id`-scoped conversation, ordered by `turn_index`.

WHY store individual turns as separate rows rather than one JSON blob
per conversation: appending a new turn becomes a single-row INSERT
instead of a read-modify-write of a growing JSON document, which
matters once conversations run long and this table is written to on
every single query. It also lets `CONVERSATION_HISTORY_MAX_TURNS`
(app/config/settings.py) be enforced with a simple, indexed
`ORDER BY turn_index DESC LIMIT N` query.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import ConversationRole

if TYPE_CHECKING:  # pragma: no cover - import-cycle avoidance only
    from app.database.models.user import User


class ConversationHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A single turn (user message or assistant reply) within a
    conversation session.

    WHY `session_id` is a plain string rather than a foreign key to
    some `Session` table: sessions in this service are lightweight and
    client-generated (e.g. a UUID minted by the frontend/orchestrator
    when a conversation starts) - there is no server-side session
    lifecycle to manage (no expiry, no login/logout), so a dedicated
    Session table would be pure overhead. `session_id` is simply the
    grouping key.
    """

    __tablename__ = "conversation_history"

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Client-supplied identifier grouping turns into one "
        "conversation. Not a foreign key by design - see class docstring.",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[ConversationRole] = mapped_column(
        Enum(ConversationRole, name="conversation_role", native_enum=False, length=20),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    turn_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based position of this turn within its session, used to "
        "reconstruct exact conversation order and to enforce "
        "CONVERSATION_HISTORY_MAX_TURNS via ORDER BY + LIMIT.",
    )

    # --- Relationships ---------------------------------------------
    user: Mapped[Optional["User"]] = relationship(back_populates="conversation_turns")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return (
            f"<ConversationHistory id={self.id} session_id={self.session_id!r} "
            f"role={self.role.value} turn={self.turn_index}>"
        )
