"""
app/database/session.py

WHY THIS FILE EXISTS
---------------------
Centralizes the ONE SQLAlchemy `Engine` and session factory for the
entire service. Every module that needs a database session - API
routes, services, ingestion - gets one exclusively through
`get_db_session` (a FastAPI dependency) rather than each constructing
its own engine/connection. WHY that matters:

    1. Connection pooling only works if there's ONE pool. Multiple
       engines would each open their own pool, multiplying real
       connections against PostgreSQL far beyond DB_POOL_SIZE and
       risking exhausting the database's max_connections.
    2. `get_db_session` guarantees the commit/rollback/close lifecycle
       happens identically on every single request - a service never
       has to remember to close a session or roll back on error.
    3. Raw SQLAlchemy connection failures (`OperationalError`, etc.)
       are caught here ONCE and converted into the typed
       `DatabaseConnectionError` from `core/exceptions.py`, so every
       route handler downstream only ever has to think in terms of
       this service's own exception hierarchy.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config.logging_config import get_logger
from app.config.settings import Settings, get_settings
from app.core.constants import PipelineStage
from app.core.exceptions import DatabaseConnectionError, DatabaseError
from app.database.base import Base

logger = get_logger(__name__)

# WHY module-level, lazily-initialized globals rather than constructing
# the engine at import time: importing this module (e.g. from a unit
# test that wants to reuse `Base` or exception types) should never have
# the SIDE EFFECT of opening real database connections. `init_engine`
# must be called explicitly (from `app/main.py` at startup, or from a
# test fixture pointing at a test database) before `get_db_session` is
# usable.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_engine(settings: Settings | None = None) -> Engine:
    """
    Create (or return the already-created) SQLAlchemy engine and
    bind the session factory to it.

    WHY idempotent: `app/main.py`'s startup event and any test fixture
    can both safely call this without worrying about double-creating
    engines/pools. Only the FIRST call with a given process actually
    builds anything; subsequent calls return the existing engine.

    Args:
        settings: Optional explicit `Settings` (primarily for tests
            that want an isolated SQLite/Postgres URL). Defaults to
            the process-wide `get_settings()` singleton.

    Returns:
        The process-wide SQLAlchemy `Engine`.
    """
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    settings = settings or get_settings()

    # WHY `pool_pre_ping=True`: without it, a connection that has gone
    # stale (e.g. the DB restarted, or a firewall silently dropped an
    # idle TCP connection) would only be discovered when a query on it
    # fails mid-request. Pre-ping does a cheap `SELECT 1` before handing
    # a pooled connection to a request, converting "random mid-request
    # failure" into "the pool transparently reconnects."
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    # WHY branch entirely on dialect here instead of passing pool_size /
    # max_overflow / pool_timeout unconditionally: SQLite (used only by
    # this service's own unit tests - see tests/ folder) does not
    # support QueuePool's sizing knobs the way PostgreSQL does, and
    # passing them raises a TypeError under SQLite's default pool
    # implementation. Building one explicit, readable kwargs dict
    # avoids an illegible nested-ternary version of this.
    engine_kwargs: dict = {"echo": settings.DB_ECHO_SQL}
    if is_sqlite:
        # WHY `check_same_thread=False`: FastAPI's TestClient and pytest
        # fixtures may hand the same SQLite connection across threads.
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs.update(
            pool_pre_ping=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
        )

    _engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        # WHY autoflush=False: prevents SQLAlchemy from silently
        # flushing pending changes mid-query (e.g. during a read that
        # happens before an explicit commit), which can otherwise
        # surface confusing partial-write errors in complex service
        # methods that build up several related objects before saving.
        autocommit=False,
        expire_on_commit=False,
        # WHY expire_on_commit=False: without this, every ORM object's
        # attributes become unusable immediately after commit (they'd
        # trigger a fresh SELECT on next access). Since `get_db_session`
        # closes the session right after the request/response cycle,
        # route handlers and services frequently need to read attributes
        # of an object AFTER it was committed (e.g. returning the newly
        # created Document's `id` in the API response) - this setting
        # keeps those attributes readable without a surprise extra query.
    )

    logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).info(
        f"Database engine initialized | dialect={_engine.dialect.name} "
        f"| pool_size={settings.DB_POOL_SIZE if not is_sqlite else 'n/a (sqlite)'}"
    )
    return _engine


def get_db_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a single request-scoped `Session`.

    WHY a generator (`yield`) rather than returning a session
    directly: this is FastAPI's standard dependency pattern for
    resources that need cleanup - code after the `yield` runs AFTER
    the route handler finishes, guaranteeing commit-or-rollback and
    close happen exactly once per request, even if the handler raised
    an exception.

    Usage (in an upcoming `api/` route):
        @router.post("/query")
        def query(payload: QueryRequest, db: Session = Depends(get_db_session)):
            ...

    Raises:
        DatabaseConnectionError: if the session cannot be used at all
            (e.g. the database is unreachable when the first query on
            it is attempted).
    """
    if _SessionLocal is None:
        # WHY this is a hard `RuntimeError`, not a `DatabaseConnectionError`:
        # this branch means `init_engine()` was never called at startup -
        # that is a programming/configuration mistake in `main.py`, not a
        # runtime database outage, and deserves to fail loudly and
        # differently so it's never confused with a transient DB issue.
        raise RuntimeError(
            "Database engine not initialized. Call init_engine() during "
            "application startup before using get_db_session()."
        )

    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except OperationalError as exc:
        session.rollback()
        logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).error(
            f"Database operational error: {exc}"
        )
        raise DatabaseConnectionError(
            "Could not communicate with the database.",
            stage=PipelineStage.METADATA_STORE_WRITE,
            original_exception=exc,
        ) from exc
    except SQLAlchemyError as exc:
        session.rollback()
        logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).error(
            f"Database error: {exc}"
        )
        raise DatabaseError(
            "A database error occurred while processing the request.",
            stage=PipelineStage.METADATA_STORE_WRITE,
            original_exception=exc,
        ) from exc
    except Exception:
        # WHY rollback here too, then re-raise unchanged: if the route
        # handler itself raised one of our OWN typed exceptions (e.g.
        # NoRetrievalResultsError), we must still roll back any partial
        # writes made earlier in that request, but we must NOT swallow
        # or re-wrap that exception - it already carries the correct,
        # specific error information for `exception_handlers.py`.
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Non-FastAPI context manager version of the same commit/rollback/
    close lifecycle as `get_db_session`, for use OUTSIDE a request
    context - e.g. a standalone ingestion script, a background worker,
    or a CLI migration helper that isn't running inside FastAPI's
    dependency injection system.

    Usage:
        with session_scope() as db:
            db.add(new_document)
    """
    if _SessionLocal is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_engine() before "
            "using session_scope()."
        )
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db_schema() -> None:
    """
    Create all tables registered on `Base.metadata`.

    WHY this exists ALONGSIDE Alembic (present in requirements.txt):
    this is explicitly a local-development / test convenience (e.g.
    spinning up a fresh SQLite database for `pytest`), NOT how staging
    or production schemas are managed. Production schema changes must
    go through Alembic migrations for proper versioning and rollback
    safety - this function is intentionally never called from
    `app/main.py`'s production startup path.
    """
    engine = init_engine()
    # WHY importing models here, inside the function, rather than at
    # module level: avoids a circular import (app.database.models
    # imports from app.database.base, which this module also imports),
    # while still guaranteeing every model is registered on
    # `Base.metadata` before `create_all` runs.
    import app.database.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema created (development/test convenience only)")


def check_database_connection() -> bool:
    """
    Lightweight connectivity check used by the `DatabaseService`
    (upcoming `services/` folder) as part of GET /health's aggregated
    subsystem health report.

    WHY a raw `SELECT 1` rather than querying an actual table: this
    should verify ONLY "can we open a connection and round-trip a
    query", not depend on any particular table existing yet - keeping
    this check meaningful even before migrations have run.

    Returns:
        True if the database is reachable, False otherwise (never
        raises - callers treat this as a boolean health signal).
    """
    if _engine is None:
        return False
    try:
        with _engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.bind(stage=PipelineStage.METADATA_STORE_WRITE.value).warning(
            f"Database health check failed: {exc}"
        )
        return False
