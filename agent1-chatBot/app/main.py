"""
app/main.py

WHY THIS FILE EXISTS
---------------------
The single entry point that turns every folder built in this project
into a running HTTP service. Run with:

    uvicorn app.main:app --host 0.0.0.0 --port 8000

WHAT HAPPENS AT STARTUP, IN ORDER
--------------------------------------
1. Settings are loaded and validated (`get_settings()` - fails fast on
   any misconfiguration, per `app/config/settings.py`'s validators).
2. Logging is configured (`configure_logging`) so every subsequent
   startup step, and every request thereafter, logs consistently.
3. The database engine is initialized (`init_engine`) - connection
   pooling is set up here, once, for the process's lifetime.
4. The full service dependency graph is constructed exactly once
   (`build_service_registry`) and stored on `app.state.service_registry`
   - see `app/api/dependencies.py` for why this is the composition
   root, not scattered per-request construction.
5. Local (non-Groq) model-backed services are warmed up
   (`warm_up_local_services`) so the FIRST real user request isn't the
   one that pays for loading the embedding/reranker models.

WHY SCHEMA CREATION IS NOT PART OF PRODUCTION STARTUP
-----------------------------------------------------------
`init_db_schema()` (see `app/database/session.py`) is explicitly NOT
called here. Production and staging schema changes must go through
Alembic migrations (in `requirements.txt`) for proper versioning and
rollback safety - calling `Base.metadata.create_all()` on every
startup would work for a quick demo but is exactly the kind of
shortcut that causes real problems the moment two instances of this
service start concurrently against a schema mid-migration. Local
development/testing environments call `init_db_schema()` explicitly
themselves (see this project's test scripts) rather than relying on
implicit behavior baked into `main.py`.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import build_service_registry
from app.api.routes import api_prefix_routers, unprefixed_routers
from app.config.logging_config import configure_logging, get_logger
from app.config.settings import get_settings
from app.core.dependencies import RequestIDMiddleware
from app.core.exception_handlers import register_exception_handlers
from app.database.session import init_engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager - code before `yield` runs at
    startup, code after runs at shutdown.

    WHY a lifespan context manager rather than the older
    `@app.on_event("startup")` decorators: lifespan is FastAPI's
    modern, recommended pattern - it guarantees startup and shutdown
    logic are defined together, in one place, making the relationship
    between "what got initialized" and "what needs cleanup" explicit
    and impossible to accidentally desynchronize across two separate
    decorated functions.
    """
    settings = get_settings()
    configure_logging(settings)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.ENVIRONMENT})")

    init_engine(settings)

    registry = build_service_registry(settings)
    registry.warm_up_local_services()
    app.state.service_registry = registry

    logger.info("Startup complete - service is ready to accept requests")
    yield

    logger.info(f"Shutting down {settings.APP_NAME}")


def create_app() -> FastAPI:
    """
    Application factory.

    WHY a factory function rather than constructing `app = FastAPI(...)`
    directly at module level: makes it possible for a test to call
    `create_app()` multiple times to get independent, isolated `FastAPI`
    instances (each with their own `app.state`) - a bare module-level
    `app` object would be a single shared singleton across an entire
    test session, risking state leaking between test cases.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Agent 1 of the IntelliPlant Multi-Agent Industrial "
        "Knowledge Intelligence Platform - a retrieval-augmented "
        "generation copilot over plant equipment, maintenance, and "
        "safety documentation.",
        lifespan=lifespan,
    )

    # WHY RequestIDMiddleware is added FIRST (making it the OUTERMOST
    # user middleware): every other middleware, every exception
    # handler, and every route handler needs `request.state.request_id`
    # to already exist by the time they run - adding it first in the
    # middleware stack guarantees it wraps everything else.
    app.add_middleware(RequestIDMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    for router in api_prefix_routers:
        app.include_router(router, prefix=settings.API_PREFIX)
    for router in unprefixed_routers:
        # WHY unprefixed: see app/api/routes/__init__.py - GET /health
        # is mounted at the bare path, matching standard infrastructure
        # health-check conventions rather than the versioned API prefix.
        app.include_router(router)

    return app


app = create_app()