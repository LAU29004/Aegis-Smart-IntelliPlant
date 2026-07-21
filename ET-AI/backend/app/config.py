"""
Central configuration for the IntelliPlant backend.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ==========================================================
# Paths
# ==========================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

STORAGE_DIR = BACKEND_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
VECTORSTORE_DIR = STORAGE_DIR / "vectorstore"
SAMPLE_DOCS_DIR = PROJECT_DIR / "sample_docs"

for directory in (UPLOAD_DIR, VECTORSTORE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# ==========================================================
# Database
# ==========================================================

DATABASE_URL = os.getenv(
    "INTELLIPLANT_DB",
    f"sqlite:///{STORAGE_DIR / 'intelliplant.db'}",
)

# ==========================================================
# JWT Authentication
# ==========================================================

JWT_SECRET = os.getenv(
    "INTELLIPLANT_JWT_SECRET",
    "intelliplant-dev-secret-change-me",
)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 12

# ==========================================================
# Google Authentication
# ==========================================================

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ==========================================================
# Anthropic
# ==========================================================

ANTHROPIC_API_KEY = os.getenv(
    "ANTHROPIC_API_KEY",
    "",
)

ANTHROPIC_MODEL = os.getenv(
    "INTELLIPLANT_MODEL",
    "claude-sonnet-5",
)

# ==========================================================
# Ollama
# ==========================================================

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "INTELLIPLANT_OLLAMA_MODEL",
    "qwen2.5:3b",
)

OLLAMA_CONTEXT_CHUNKS = int(
    os.getenv(
        "INTELLIPLANT_OLLAMA_CHUNKS",
        "3",
    )
)

OLLAMA_CHUNK_CHARS = int(
    os.getenv(
        "INTELLIPLANT_OLLAMA_CHUNK_CHARS",
        "700",
    )
)

OLLAMA_TIMEOUT = int(
    os.getenv(
        "INTELLIPLANT_OLLAMA_TIMEOUT",
        "90",
    )
)

DISABLE_OLLAMA = (
    os.getenv(
        "INTELLIPLANT_DISABLE_OLLAMA",
        "0",
    )
    == "1"
)

# ==========================================================
# Retrieval Configuration
# ==========================================================

CHUNK_SIZE_WORDS = int(
    os.getenv(
        "CHUNK_SIZE_WORDS",
        "380",
    )
)

CHUNK_OVERLAP_WORDS = int(
    os.getenv(
        "CHUNK_OVERLAP_WORDS",
        "40",
    )
)

TOP_K_RETRIEVE = int(
    os.getenv(
        "TOP_K_RETRIEVE",
        "15",
    )
)

TOP_K_CONTEXT = int(
    os.getenv(
        "TOP_K_CONTEXT",
        "5",
    )
)

# ==========================================================
# Alert Configuration
# ==========================================================

ALERT_DUPLICATE_WINDOW_HOURS = int(
    os.getenv(
        "ALERT_DUPLICATE_WINDOW_HOURS",
        "24",
    )
)

PATTERN_ALERT_SEVERITY = os.getenv(
    "PATTERN_ALERT_SEVERITY",
    "warning",
).lower()

# ==========================================================
# Scheduler
# ==========================================================

MAINTENANCE_SCAN_INTERVAL_MINUTES = int(
    os.getenv(
        "MAINTENANCE_SCAN_INTERVAL_MINUTES",
        "5",
    )
)

# ==========================================================
# CORS
# ==========================================================

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://aegis-smart-intelli-plant-vert.vercel.app"
]