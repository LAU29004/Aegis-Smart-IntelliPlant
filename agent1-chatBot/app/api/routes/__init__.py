"""
app/api/routes package.

WHY a dedicated `routes` subpackage: one file per resource
(`query_routes.py`, `upload_routes.py`, `document_routes.py`,
`history_routes.py`, `health_routes.py`), each holding a single
`APIRouter` with a single responsibility - mirrors this codebase's
consistent one-concern-per-file convention throughout every other
folder. `app/main.py` imports ONLY the aggregated `all_routers` list
below, so adding a new route file never requires touching `main.py`'s
import list beyond this one central registration point.
"""

from app.api.routes.document_routes import router as document_router
from app.api.routes.health_routes import router as health_router
from app.api.routes.history_routes import router as history_router
from app.api.routes.query_routes import router as query_router
from app.api.routes.upload_routes import router as upload_router

# WHY health is listed separately (not in `api_prefix_routers`): see
# app/main.py - GET /health is deliberately mounted WITHOUT the
# versioned API prefix (e.g. `/api/v1`), matching the near-universal
# infrastructure convention (Kubernetes, load balancers, uptime
# monitors) of probing an unversioned, unprefixed `/health` endpoint.
api_prefix_routers = [query_router, upload_router, document_router, history_router]
unprefixed_routers = [health_router]

__all__ = ["api_prefix_routers", "unprefixed_routers"]
