"""IntelliPlant backend — FastAPI application entry point.

Run:  uvicorn app.main:app --reload --port 8000  (from the backend/ folder)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import CORS_ORIGINS
from .database import init_db
from .envelope import err, ok
from .routers import (alerts, analytics, auth, compliance, documents, equipment,
                      incidents, ingest, query,notifications)
from .seed import seed_all
from .services.embeddings import get_backend
from .services.llm import llm_mode
from .services.vectorstore import get_store_backend
from .services.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    init_db()

    # Seed demo/sample data
    seed_all()

    print(
        f"[intelliplant] vector store: {get_store_backend()} | "
        f"embeddings: {get_backend()} | "
        f"llm: {llm_mode()}"
    )

    # Start background maintenance scheduler
    start_scheduler()

    try:
        yield

    finally:
        # Gracefully stop scheduler during shutdown
        stop_scheduler()


app = FastAPI(title="IntelliPlant API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Accept any localhost / 127.0.0.1 / LAN-IP origin on any port (dev convenience).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\d+\.\d+\.\d+\.\d+)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=err(str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=err("Invalid request: " + str(exc.errors()[:2])))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=err(f"Internal error: {exc}"))


API = "/api/v1"
for r in (auth.router, ingest.router, query.router, equipment.router,
          compliance.router, alerts.router, documents.router,
          incidents.router, analytics.router,notifications.router):
    app.include_router(r, prefix=API)


@app.get("/")
def root():
    return ok({
        "service": "IntelliPlant API",
        "version": "1.0.0",
        "vector_store": get_store_backend(),
        "embeddings": get_backend(),
        "llm": llm_mode(),
        "docs": "/docs",
    })
