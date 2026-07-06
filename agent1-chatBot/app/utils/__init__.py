"""
app/utils package.

WHY a dedicated `utils` package: holds small, stateless, dependency-
free helper functions with NO framework dependency (no FastAPI, no
SQLAlchemy session, no injected `Settings`-backed service) - a pure
function of its arguments, testable in complete isolation. This is
what distinguishes `utils/` from `core/`: `core/dependencies.py`'s
`get_request_id`/`Stopwatch` are genuine FastAPI dependency-injection
surface; everything here is plain Python any part of the codebase (or
a future Agent 2/3/4) can import and call directly, with zero setup.
"""

from app.utils.file_validation import get_file_extension, validate_upload
from app.utils.filename_utils import build_storage_filename, sanitize_filename
from app.utils.hashing import sha256_hex
from app.utils.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, apply_pagination
from app.utils.text_utils import truncate

__all__ = [
    "get_file_extension",
    "validate_upload",
    "build_storage_filename",
    "sanitize_filename",
    "sha256_hex",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "apply_pagination",
    "truncate",
]
