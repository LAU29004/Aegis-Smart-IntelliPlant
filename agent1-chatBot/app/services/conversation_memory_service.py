"""
app/services/conversation_memory_service.py

WHY THIS FILE EXISTS
---------------------
Implements "Conversation Memory" - one of the six capabilities the
spec's Most Important Requirement explicitly names as something
Agent 2/3/4 and a future orchestrator must be able to reuse without
code duplication. It is backed by the `ConversationHistory` table
(see `app/database/models/conversation.py`) and does exactly two
things: read back the last N turns for a session, and append a new
turn - nothing more.

WHY THIS SERVICE DOES NOT HOLD A DATABASE SESSION AS INSTANCE STATE
----------------------------------------------------------------------
Every other service in this codebase (`RetrievalService`,
`GroqLLMService`, etc.) is constructed once and reused across many
requests - that works because they hold long-lived resources (a
loaded model, an HTTP client) that are safe and desirable to share.
A SQLAlchemy `Session`, by contrast, is explicitly request-scoped
(see `app/database/session.py::get_db_session`) - it must NOT be
held across requests or shared between them. So this service takes
`db: Session` as a per-call PARAMETER on every method instead of a
constructor argument, staying a stateless, reusable service object
while still operating correctly within FastAPI's one-session-per-
request lifecycle.
"""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import ConversationMemoryError
from app.database.enums import ConversationRole
from app.database.models import ConversationHistory
from app.prompts.schemas import ConversationTurn


class ConversationMemoryService(BaseService):
    """
    Reads and appends conversation turns for a given session, bounded
    to `Settings.CONVERSATION_HISTORY_MAX_TURNS`.
    """

    def get_recent_history(
        self,
        db: Session,
        session_id: str,
        max_turns: Optional[int] = None,
    ) -> List[ConversationTurn]:
        """
        Fetch the most recent turns for a session, in chronological
        order (oldest first) - the order `PromptBuilderService.build_messages`
        expects for replaying prior turns into the LLM message list.

        Args:
            db: Request-scoped SQLAlchemy session.
            session_id: The conversation's client-supplied grouping id.
            max_turns: Override for
                `Settings.CONVERSATION_HISTORY_MAX_TURNS`.

        Returns:
            Up to `max_turns` `ConversationTurn` objects, oldest first.
            Returns an empty list for a session with no prior history
            (this is the normal case for a conversation's first turn,
            not an error).

        Raises:
            ConversationMemoryError: on a database failure.
        """
        effective_max_turns = (
            max_turns if max_turns is not None else self.settings.CONVERSATION_HISTORY_MAX_TURNS
        )
        if effective_max_turns <= 0 or not session_id:
            return []

        try:
            # WHY fetch DESC + reverse in Python, rather than querying
            # ASC with an OFFSET: we want the MOST RECENT N turns, but
            # need to hand them back in chronological order. Querying
            # DESC with LIMIT correctly selects "the last N" turns
            # regardless of how long the full conversation has grown;
            # an ASC query would instead need to know the total count
            # up front to compute a correct OFFSET.
            rows = db.execute(
                select(ConversationHistory)
                .where(ConversationHistory.session_id == session_id)
                .order_by(ConversationHistory.turn_index.desc())
                .limit(effective_max_turns)
            ).scalars().all()
        except SQLAlchemyError as exc:
            raise ConversationMemoryError(
                "Failed to load conversation history.",
                stage=PipelineStage.CONTEXT_BUILDING,
                details={"session_id": session_id},
                original_exception=exc,
            ) from exc

        chronological_rows = list(reversed(rows))
        return [
            ConversationTurn(role=row.role.value, content=row.message)
            for row in chronological_rows
        ]

    def append_turn(
        self,
        db: Session,
        session_id: str,
        role: ConversationRole,
        content: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> ConversationHistory:
        """
        Append one new turn to a session's history.

        WHY this method does NOT call `db.commit()`: per this
        codebase's session-lifecycle convention (see
        `app/database/session.py::get_db_session`), the caller's
        request-scoped session owns the commit/rollback boundary -
        typically the caller wants to persist a `QueryLog` row AND
        both new conversation turns (user question + assistant answer)
        as one atomic unit, which only works if none of them commit
        independently mid-transaction.

        Args:
            db: Request-scoped SQLAlchemy session.
            session_id: The conversation's grouping id.
            role: `ConversationRole.USER` or `.ASSISTANT`.
            content: The turn's message text.
            user_id: Optional user this turn belongs to.

        Returns:
            The newly created (but not yet committed) `ConversationHistory`
            row.

        Raises:
            ConversationMemoryError: on a database failure, or if
                `session_id`/`content` is empty.
        """
        if not session_id or not content or not content.strip():
            raise ConversationMemoryError(
                "Cannot append a conversation turn with an empty "
                "session_id or content.",
                stage=PipelineStage.CONTEXT_BUILDING,
            )

        try:
            # WHY compute next turn_index via a query rather than
            # tracking it in memory: this service is stateless (see
            # module docstring) and may be called concurrently for
            # different sessions - the database is the only source of
            # truth for "how many turns does this session already have".
            existing_max = db.execute(
                select(ConversationHistory.turn_index)
                .where(ConversationHistory.session_id == session_id)
                .order_by(ConversationHistory.turn_index.desc())
                .limit(1)
            ).scalar_one_or_none()
            next_turn_index = 0 if existing_max is None else existing_max + 1

            turn = ConversationHistory(
                session_id=session_id,
                user_id=user_id,
                role=role,
                message=content.strip(),
                turn_index=next_turn_index,
            )
            db.add(turn)
            db.flush()  # WHY flush (not commit): assigns turn.id and
            # validates constraints immediately, surfacing any DB error
            # right here rather than silently at the caller's eventual
            # commit, while still leaving the transaction open for the
            # caller to add more rows atomically.
        except SQLAlchemyError as exc:
            raise ConversationMemoryError(
                "Failed to append conversation turn.",
                stage=PipelineStage.CONTEXT_BUILDING,
                details={"session_id": session_id, "role": role.value},
                original_exception=exc,
            ) from exc

        return turn

    def health_check(self) -> dict:
        """
        WHY this health check does NOT touch the database: unlike
        every other service's health check in this codebase,
        `ConversationMemoryService` has no long-lived resource of its
        own to probe (no model, no client) - it is a stateless query/
        append wrapper around whatever `Session` a caller provides.
        Database connectivity itself is already covered by
        `app.database.session.check_database_connection`, called
        directly by the composition root's aggregated health check -
        duplicating that check here would just be redundant.
        """
        return {
            "service": self.service_name,
            "healthy": True,
            "details": {
                "conversation_history_max_turns": self.settings.CONVERSATION_HISTORY_MAX_TURNS
            },
        }
