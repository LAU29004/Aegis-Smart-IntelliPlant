"""
app/utils/hashing.py

WHY THIS FILE EXISTS
---------------------
A single, obvious place for the SHA-256 content-hashing logic that
backs `Document.content_hash`-based upload deduplication (see
`app/database/models/document.py` and
`DocumentUploadPipelineService.upload_document`). Trivial as the
implementation is, centralizing it means if this codebase ever needed
a DIFFERENT hash algorithm (e.g. a faster non-cryptographic hash for
some future high-throughput use case), there is exactly one call site
to change rather than a `hashlib.sha256(...)` call duplicated across
`services/` and any future ingestion entry point (e.g. a bulk-import
script) that also needs identical, dedup-compatible hashing.
"""

import hashlib


def sha256_hex(data: bytes) -> str:
    """
    Compute the SHA-256 hex digest of `data`.

    Args:
        data: Raw bytes to hash - typically an uploaded file's full
            content.

    Returns:
        A 64-character lowercase hex digest, matching the exact
        format `Document.content_hash` (see
        `app/database/models/document.py`, `String(64)`) expects.
    """
    return hashlib.sha256(data).hexdigest()
