"""
app/utils/pagination.py

WHY THIS FILE EXISTS
---------------------
`GET /documents` (and potentially other future list endpoints) needs
consistent, bounded pagination applied to a SQLAlchemy `select()`
statement. Rather than every route handler in the upcoming `api/`
folder writing its own `.limit(...).offset(...)` calls with its own
ad-hoc bounds-checking, this is the ONE place that logic lives.

WHY THIS ENFORCES A HARD MAXIMUM INDEPENDENT OF `DocumentListQueryParams`
--------------------------------------------------------------------------
`app.schemas.document_schemas.DocumentListQueryParams` already caps
`limit` at 200 via Pydantic's `le=200` - so in the NORMAL request path
through FastAPI, an over-large limit is already rejected before this
function ever runs. This function's own `MAX_PAGE_SIZE` clamp exists
as defense in depth for any OTHER caller of this utility that isn't
going through that Pydantic validation (e.g. a future internal script,
or Agent 2/3/4 reusing this helper directly) - it should never be
possible to accidentally construct an unbounded query through this
function, regardless of which layer calls it.
"""

from sqlalchemy import Select

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


def apply_pagination(stmt: Select, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0) -> Select:
    """
    Apply bounded `LIMIT`/`OFFSET` to a SQLAlchemy `select()` statement.

    Args:
        stmt: The base `select()` statement to paginate.
        limit: Requested page size - clamped to `[1, MAX_PAGE_SIZE]`.
        offset: Requested offset - clamped to a minimum of 0.

    Returns:
        `stmt` with `.limit(...)` and `.offset(...)` applied.
    """
    clamped_limit = max(1, min(limit, MAX_PAGE_SIZE))
    clamped_offset = max(0, offset)
    return stmt.limit(clamped_limit).offset(clamped_offset)
