"""
app/database package.

WHY a dedicated `database` package: this is the ONLY part of the
codebase allowed to know about SQLAlchemy, connection pooling, and
Postgres-specific concerns. `services/` and `api/` (upcoming folders)
interact with persistence exclusively through:

    - the ORM models re-exported below (`Document`, `Chunk`, `User`,
      `ConversationHistory`, `QueryLog`, `Feedback`)
    - `get_db_session` (FastAPI dependency) / `session_scope`
      (non-FastAPI context manager)
    - `init_engine`, `init_db_schema`, `check_database_connection`
      (lifecycle/health helpers)

This keeps the relational storage technology an implementation detail
that could, in principle, be swapped later without touching business
logic in `services/` - which only ever imports names from here.
"""

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.database.enums import (
    ConversationRole,
    DocumentStatus,
    FeedbackRating,
    UserRole,
)
from app.database.models import (
    Chunk,
    ConversationHistory,
    Document,
    Feedback,
    QueryLog,
    User,
)
from app.database.session import (
    check_database_connection,
    get_db_session,
    init_db_schema,
    init_engine,
    session_scope,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "ConversationRole",
    "DocumentStatus",
    "FeedbackRating",
    "UserRole",
    "Chunk",
    "ConversationHistory",
    "Document",
    "Feedback",
    "QueryLog",
    "User",
    "check_database_connection",
    "get_db_session",
    "init_db_schema",
    "init_engine",
    "session_scope",
]
