"""
app/api/routes/health_routes.py

WHY THIS FILE EXISTS
---------------------
Implements `GET /health`. WHY this offers TWO distinct check depths
via a `deep` query parameter rather than always running the full
aggregated check:

    - `GET /health` (default, `deep=false`): checks ONLY database
      connectivity - a fast, cheap check safe to poll frequently (e.g.
      a Kubernetes liveness/readiness probe every few seconds) without
      generating real load against Groq, the embedding model, or the
      cross-encoder.
    - `GET /health?deep=true`: runs EVERY registered service's
      `health_check()`, including `GroqLLMService`'s (a REAL, billed
      Groq API call) and the embedding/reranker services' (real model
      inference calls) - genuinely useful for on-demand diagnostics or
      a deploy-time smoke test, but far too expensive to run on every
      routine liveness probe.

Conflating these into one always-deep check would force operators to
choose between an unhelpfully shallow health endpoint or a needlessly
expensive one - offering both means each caller gets the check depth
appropriate to why they're asking.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request

from app.config.settings import get_settings
from app.database.session import check_database_connection
from app.schemas.health_schemas import HealthCheckResponse
from app.api.dependencies import ServiceRegistry

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Service health check",
    description="Returns overall service health. By default, checks only "
    "database connectivity (cheap, safe for frequent polling). Pass "
    "?deep=true for a full check including real Groq/embedding model "
    "round-trips (slower, incurs real API usage).",
)
def health_check(
    request: Request,
    deep: bool = Query(
        default=False,
        description="If true, run full sub-service health checks including "
        "real Groq and embedding model calls. If false (default), check "
        "only database connectivity.",
    ),
) -> HealthCheckResponse:
    settings = get_settings()
    checks: dict = {
        "database": {"healthy": check_database_connection(), "details": {}},
    }

    if deep:
        registry: ServiceRegistry = request.app.state.service_registry
        checks["query_pipeline"] = registry.query_pipeline_service.health_check()
        checks["document_upload_pipeline"] = registry.upload_pipeline_service.health_check()

    overall_healthy = all(check.get("healthy", False) for check in checks.values())

    return HealthCheckResponse(
        status="healthy" if overall_healthy else "unhealthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        timestamp=datetime.now(timezone.utc),
        checks=checks,
    )
