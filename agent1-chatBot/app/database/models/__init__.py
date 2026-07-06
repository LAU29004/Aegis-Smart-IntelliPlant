"""
app/database/models/__init__.py

WHY THIS FILE EXISTS
---------------------
SQLAlchemy's `Base.metadata.create_all()` (used by `init_db` in
`session.py` for local/dev bootstrapping) and Alembic's autogenerate
(used in real migrations, per requirements.txt) both need every model
class to have been IMPORTED at least once so it registers itself onto
`Base.metadata`. Without this aggregating import, a model file that no
other module happens to import would be silently invisible to both
`create_all()` and Alembic - producing a confusing "table doesn't
exist" error at runtime instead of a clear startup failure.

Every other part of the codebase should import models FROM HERE
(`from app.database.models import Document, Chunk, ...`) rather than
reaching into individual model files directly - this is the one
public surface for the entire ORM layer.
"""

from app.database.models.chunk import Chunk
from app.database.models.conversation import ConversationHistory
from app.database.models.document import Document
from app.database.models.feedback import Feedback
from app.database.models.query_log import QueryLog
from app.database.models.user import User

__all__ = [
    "Chunk",
    "ConversationHistory",
    "Document",
    "Feedback",
    "QueryLog",
    "User",
]
