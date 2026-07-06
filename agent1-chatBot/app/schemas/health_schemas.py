"""
app/schemas/health_schemas.py

WHY THIS FILE EXISTS
---------------------
Defines the response model for `GET /health`. WHY `checks` is typed as
a loosely-structured `Dict[str, Any]` rather than a fully-typed nested
model per sub-service: the aggregated health payload's shape is
inherently recursive and heterogeneous (`QueryPipelineService.health_check()`
nests `RetrievalService.health_check()`, which itself nests THREE more
sub-service checks, each with its own `details` dict whose keys differ
per service - an embedding service reports a model name and dimension,
a database check reports a vector count). Modeling that exactly in
Pydantic would require a parallel type hierarchy mirroring EVERY
`BaseService.health_check()` implementation's return shape, providing
no real validation benefit (this is diagnostic output, not something
a client parses field-by-field) for a lot of ongoing maintenance
burden every time a service's health details change.
"""

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckResponse(BaseModel):
    """Response body for `GET /health`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "IntelliPlant Agent 1 - RAG Copilot",
                "version": "1.0.0",
                "timestamp": "2026-07-03T10:15:00Z",
                "checks": {
                    "database": {"healthy": True, "details": {}},
                    "query_pipeline": {"healthy": True, "details": {}},
                    "document_upload_pipeline": {"healthy": True, "details": {}},
                },
            }
        }
    )

    status: str = Field(..., description="'healthy' or 'unhealthy' - the overall rollup.")
    service: str
    version: str
    timestamp: datetime
    checks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-subsystem health detail, one entry per top-level "
        "service registered with the application (database connectivity, "
        "query pipeline, upload pipeline).",
    )
