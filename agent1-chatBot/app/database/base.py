"""
app/database/base.py

WHY THIS FILE EXISTS
---------------------
Every SQLAlchemy model in `app/database/models/` inherits from the
SAME `Base` declarative class defined here. This is not optional in
SQLAlchemy - all mapped classes that participate in the same
`Base.metadata` (needed for `create_all`, Alembic autogeneration, and
cross-table relationships/foreign keys) must share one `Base`.

This file also defines two mixins used by EVERY model:

    - `UUIDPrimaryKeyMixin`: every table in this schema uses a UUID
      primary key rather than an auto-incrementing integer. WHY:
      UUIDs can be generated client-side (e.g. by the ingestion
      pipeline BEFORE a row is committed, so the same id can be used
      as the ChromaDB document/chunk id - keeping the vector store and
      the relational store referencing an identical key). Integer
      auto-increment ids can't be known until after an INSERT commits.

    - `TimestampMixin`: `created_at` / `updated_at` are needed on
      almost every table for auditing (when was this document
      uploaded, when was this feedback given) and the spec's Logging
      section implicitly requires traceability of when things
      happened. Defining this ONCE avoids six copy-pasted pairs of
      columns across six model files.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    """
    Shared declarative base for every ORM model in this service.

    WHY a bare subclass with no extra logic: SQLAlchemy 2.0's
    `DeclarativeBase` already provides everything models need
    (`metadata`, type-annotation-driven mapping via `Mapped[...]`).
    Keeping this class empty means there is exactly one obvious place
    new cross-model configuration (e.g. a shared naming convention for
    constraints, used by Alembic autogeneration) would go later,
    without disturbing every existing model.
    """

    pass


def _utcnow() -> datetime:
    """
    WHY a named function instead of `datetime.utcnow` directly as the
    column default: `datetime.utcnow()` returns a NAIVE datetime
    (no tzinfo), which silently causes timezone bugs once this data is
    compared against timezone-aware datetimes elsewhere in the
    codebase (e.g. `datetime.now(timezone.utc)` used in
    `exception_handlers.py`). This helper guarantees every timestamp
    written by the ORM is timezone-AWARE UTC, consistently.
    """
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    """
    Adds a UUID primary key column named `id` to any model that
    inherits this mixin.

    WHY `default=uuid.uuid4` (Python-side) rather than a database
    server-side default (e.g. Postgres `gen_random_uuid()`): the id
    needs to be known to application code BEFORE the row is flushed to
    the database - specifically, the ingestion pipeline (upcoming
    `ingestion/` folder) generates a Chunk's UUID first, uses that
    exact same UUID as the id it writes into ChromaDB, and only then
    persists the Chunk row to Postgres. A server-side default would
    make that ordering impossible without an extra round-trip.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` columns to any model.

    WHY `updated_at` uses `onupdate=_utcnow` (an ORM-level hook) rather
    than a DB trigger: keeps the "how do timestamps get set" logic
    entirely within the Python/SQLAlchemy layer, visible in one place,
    with no hidden database-side triggers that a future engineer might
    not know to look for when debugging.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
