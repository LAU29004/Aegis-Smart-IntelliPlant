"""
Config package.

WHY a dedicated `config` package instead of scattering `os.getenv()`
calls across the codebase:
    1. Single source of truth - every module that needs a setting
       (chunk size, Groq model name, DB URL, confidence thresholds...)
       imports the SAME validated `Settings` object. This prevents the
       classic bug where one module reads `CHUNK_SIZE=512` and another
       silently defaults to a different value because it typo'd the
       env var name.
    2. Type safety - Pydantic validates types and ranges at process
       startup, not at 2am in production when a malformed .env value
       finally gets exercised by a request.
    3. Testability - services depend on an injected `Settings` object
       (see `get_settings` below), so tests can construct a `Settings`
       instance with overrides without touching real environment
       variables or files on disk.
    4. Orchestrator readiness - when Agent 2/3/4 or a central
       orchestrator import this service, they get one canonical,
       cached settings object rather than re-parsing env vars.
"""

from app.config.settings import Settings, get_settings
from app.config.logging_config import configure_logging, get_logger

__all__ = [
    "Settings",
    "get_settings",
    "configure_logging",
    "get_logger",
]