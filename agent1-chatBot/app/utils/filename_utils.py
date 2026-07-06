"""
app/utils/filename_utils.py

WHY THIS FILE EXISTS
---------------------
Two distinct filename concerns, both needed by
`DocumentUploadPipelineService` (and any future code that handles
uploaded files):

    1. `sanitize_filename` - makes a user-supplied filename SAFE to
       display/log/store as `Document.original_filename` - stripping
       path separators and other characters that could otherwise
       enable a path-traversal attempt if a filename were ever used to
       construct a filesystem path elsewhere.
    2. `build_storage_filename` - generates the ACTUAL on-disk/object-
       storage filename, deliberately based on the content hash rather
       than the (sanitized but still attacker-influenced) original
       name, so storage paths are fully predictable and collision-free
       regardless of what a user named their file.
"""

from pathlib import Path

from slugify import slugify

from app.utils.file_validation import get_file_extension


def sanitize_filename(filename: str) -> str:
    """
    Produce a safe, display-friendly version of an uploaded filename.

    WHY `slugify` is applied only to the STEM, with the extension
    reattached afterward (not the whole filename slugified together):
    `slugify` lowercases and replaces most punctuation with hyphens -
    applying it to the WHOLE filename would turn `"Pump Manual.pdf"`
    into `"pump-manual-pdf"`, losing the actual file extension
    entirely, which downstream code (`get_file_extension`,
    `DocumentUploadPipelineService`'s PDF-vs-image routing) depends on
    being a real, recognizable extension.

    Args:
        filename: The original, untrusted uploaded filename.

    Returns:
        A filesystem- and display-safe filename, e.g.
        `"Pump Manual (v2).pdf"` -> `"pump-manual-v2.pdf"`.
    """
    path = Path(filename)
    extension = path.suffix.lower()
    safe_stem = slugify(path.stem) or "unnamed-file"
    return f"{safe_stem}{extension}"


def build_storage_filename(content_hash: str, original_filename: str) -> str:
    """
    Build the actual on-disk/object-storage filename for an uploaded
    document.

    WHY based on `content_hash` rather than `sanitize_filename`'s
    output: two different users could plausibly upload two different
    files that sanitize to the identical name (e.g. both named
    "manual.pdf"). Since `content_hash` is already guaranteed unique
    per distinct file content by `Document.content_hash`'s unique
    constraint (see `app/database/models/document.py`), reusing it
    here as the storage filename guarantees collision-free storage
    paths for free, with no additional uniqueness logic needed.

    Args:
        content_hash: The SHA-256 hex digest of the file's content.
        original_filename: Used only to determine the extension to
            preserve (e.g. so the stored file is still recognizable as
            a `.pdf` by any tooling that inspects the storage directory
            directly).

    Returns:
        A storage filename like
        `"a1b2c3...d4e5f6.pdf"`.
    """
    extension = get_file_extension(original_filename)
    return f"{content_hash}{extension}"
