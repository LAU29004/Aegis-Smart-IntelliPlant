"""
app/config/logging_config.py

WHY THIS FILE EXISTS
---------------------
The spec requires every pipeline stage (Upload, OCR, Chunking,
Embedding, Retrieval, Prompt, LLM, Response Time, Errors) to be
logged. Rather than each module calling `print()` or configuring its
own `logging.Logger`, every module in this codebase does:

    from app.config.logging_config import get_logger
    logger = get_logger(__name__)

This guarantees:
    1. One consistent log format across the entire service (so logs
       from ingestion, retrieval, and the LLM layer are trivially
       correlated by timestamp/request id in a log aggregator).
    2. One place to change the log format, sinks, or rotation policy.
    3. Standard library `logging` calls made by third-party
       dependencies (FastAPI, SQLAlchemy, uvicorn, sentence-transformers)
       are intercepted and routed through the same Loguru sinks, so we
       never end up with two divergent log streams.
    4. A future orchestrator or Agent 2/3/4 that reuses these service
       classes gets identical structured logging for free, since the
       services themselves never assume a particular logging backend
       beyond `get_logger`.
"""

import logging
import sys
from pathlib import Path

from loguru import logger as _loguru_logger

from app.config.settings import Settings

# WHY module-level flag: `configure_logging` may be called multiple
# times (e.g. once by the FastAPI app, once by a test fixture, once by
# a standalone ingestion script). Guarding against re-configuration
# prevents duplicate sinks -> duplicated log lines.
_LOGGING_CONFIGURED = False


class _InterceptStdLibHandler(logging.Handler):
    """
    Redirects standard-library `logging` records into Loguru.

    WHY: Libraries this project depends on (uvicorn, SQLAlchemy,
    sentence-transformers, chromadb) use the stdlib `logging` module
    internally. Without this bridge, their log lines would bypass our
    formatting/rotation/JSON settings entirely and show up in a
    completely different style (or not at all if a sink hasn't been
    attached to the root stdlib logger).
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Translate the stdlib level name to a Loguru level, falling
        # back to the numeric level if Loguru doesn't recognize the
        # name (this can happen with custom third-party log levels).
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find the actual caller so Loguru reports the correct
        # source file/line instead of pointing at this shim.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(settings: Settings) -> None:
    """
    Configure Loguru sinks for the entire process.

    WHY the specific sinks chosen below:
        - A colorized console sink for local development readability.
        - A rotating file sink for `INFO` and above, so operational
          history survives container restarts (mounted volume) and
          can be tailed/shipped by a log collector.
        - A SEPARATE rotating file sink for `ERROR` and above only.
          The spec explicitly calls out "Errors" as a stage that must
          be logged; isolating errors into their own file means
          on-call engineers can `tail -f logs/errors.log` without
          wading through routine INFO noise.

    Args:
        settings: The validated application Settings, so log level,
            directory, rotation, retention, and JSON-vs-text format
            are all driven by configuration rather than hardcoded here.
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    log_dir = Path(settings.LOG_DIRECTORY)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove Loguru's default stderr sink so we fully control output
    # format instead of getting both the default AND our custom sink.
    _loguru_logger.remove()

    # WHY this format: includes UTC timestamp, level, module:function:line
    # (critical for tracing which pipeline stage emitted a log line),
    # and the message itself. `{extra}` surfaces any bound context such
    # as request_id or document_id (see get_logger usage in services).
    text_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "{extra} | <level>{message}</level>"
    )

    # --- Console sink -----------------------------------------------
    _loguru_logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=text_format,
        colorize=True,
        backtrace=True,
        diagnose=not settings.is_production,  # never leak variable
        # values in production tracebacks - security best practice.
        enqueue=True,  # thread/process-safe writes under FastAPI's
        # async workers.
    )

    # --- General rotating file sink ----------------------------------
    _loguru_logger.add(
        str(log_dir / "agent1_rag_copilot.log"),
        level=settings.LOG_LEVEL,
        format=text_format if not settings.LOG_JSON_FORMAT else None,
        serialize=settings.LOG_JSON_FORMAT,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        backtrace=True,
        diagnose=not settings.is_production,
        enqueue=True,
    )

    # --- Dedicated error-only file sink -------------------------------
    # WHY: satisfies the explicit "Errors" logging requirement from
    # the spec as a first-class, independently rotated stream.
    _loguru_logger.add(
        str(log_dir / "agent1_errors.log"),
        level="ERROR",
        format=text_format if not settings.LOG_JSON_FORMAT else None,
        serialize=settings.LOG_JSON_FORMAT,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        backtrace=True,
        diagnose=not settings.is_production,
        enqueue=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, chromadb, etc.) through
    # the same Loguru sinks configured above.
    logging.basicConfig(handlers=[_InterceptStdLibHandler()], level=0, force=True)
    for noisy_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        std_logger = logging.getLogger(noisy_logger_name)
        std_logger.handlers = [_InterceptStdLibHandler()]
        std_logger.propagate = False

    _LOGGING_CONFIGURED = True
    _loguru_logger.bind(stage="startup").info(
        f"Logging configured | level={settings.LOG_LEVEL} "
        f"| directory={log_dir} | json={settings.LOG_JSON_FORMAT}"
    )


def get_logger(name: str):
    """
    Return a Loguru logger bound with the calling module's name.

    WHY a thin wrapper instead of importing `loguru.logger` directly
    everywhere: it gives every module a consistent `name` binding
    (mirrors stdlib `logging.getLogger(__name__)` ergonomics) and
    creates one obvious place to extend binding behavior later (e.g.
    automatically attaching a request_id from a context variable)
    without touching every call site across ingestion/, retrieval/,
    llm/, etc.

    Usage:
        logger = get_logger(__name__)
        logger.info("Chunk embedded successfully", chunk_id=chunk_id)

    Args:
        name: Typically `__name__` of the calling module.

    Returns:
        A Loguru logger instance pre-bound with `name`.
    """
    return _loguru_logger.bind(name=name)
