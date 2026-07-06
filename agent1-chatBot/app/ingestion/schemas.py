"""
app/ingestion/schemas.py

WHY THIS FILE EXISTS
---------------------
The ingestion pipeline (Upload -> OCR if required -> Text Extraction
-> Cleaning -> Chunking -> Metadata Extraction -> Embedding -> Store
in ChromaDB -> Store Metadata in PostgreSQL) has several distinct
stages, each owned by its own service in this folder. These
dataclasses are the typed hand-off objects between those stages, kept
here (rather than inline in each service) so every service in this
folder agrees on the exact same shape without circular imports between
service modules.

WHY plain dataclasses rather than Pydantic models: identical rationale
to `app/embeddings/schemas.py` and `app/retrieval/schemas.py` - these
flow purely between trusted, first-party services within a single
process. They are never the FastAPI request/response boundary (that
is what `app/schemas/`, an upcoming folder, is for), so Pydantic's
validation overhead is unnecessary here.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ExtractedPage:
    """
    Raw text extracted from a single page (or, for a standalone image
    upload, the single implicit "page").

    Attributes:
        page_number: 1-indexed page number within the source document.
        text: The raw extracted text for this page, BEFORE cleaning.
        used_ocr: True if this page's text came from Tesseract OCR
            rather than PyMuPDF's native text layer - i.e. this was a
            scanned page. Surfaced through to `Document.status`/logs
            so ingestion quality (how much of a document required OCR,
            which is typically lower-fidelity than a native text
            layer) is visible and auditable, not silently invisible.
    """

    page_number: int
    text: str
    used_ocr: bool


@dataclass(frozen=True)
class ExtractedDocument:
    """
    The full result of the Text Extraction (+ OCR) stages, before
    cleaning - one `ExtractedPage` per source page, in order.
    """

    pages: List[ExtractedPage] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def ocr_page_count(self) -> int:
        """WHY exposed as a property rather than tracked separately by
        callers: this is a derived fact about the pages list itself -
        computing it here means it can never drift out of sync with
        the actual page data it's describing."""
        return sum(1 for page in self.pages if page.used_ocr)


@dataclass(frozen=True)
class ChunkRecord:
    """
    One chunk produced by the Chunking stage, ready to be persisted
    (by the upcoming `services/` orchestration layer, which assigns
    the actual `Chunk.id` / `chroma_vector_id` and attaches document-
    level metadata such as department/equipment_id/upload_date).

    WHY this does NOT carry `document_name`, `department`,
    `equipment_id`, `upload_date`, or `document_type`: those are
    DOCUMENT-level facts, known by the caller of
    `DocumentIngestionService.ingest(...)` BEFORE ingestion even
    starts (they come from the upload request, not from the file's
    content) - repeating them on every single `ChunkRecord` here would
    just be redundant plumbing the chunker has no business knowing
    about. The persistence layer merges chunk-level fields (below)
    with document-level fields when constructing the final `Chunk` ORM
    row and ChromaDB metadata payload.

    Attributes:
        chunk_index: 0-based position of this chunk within the
            document's full chunk sequence.
        content: The chunk's cleaned text (~512 tokens, 50-token
            overlap with adjacent chunks).
        token_count: Actual token count of `content`, as measured by
            the chunker's tokenizer.
        page_number: The page this chunk's content BEGINS on. A chunk
            may span a page boundary (since chunking operates on the
            document's continuous token stream, not independently per
            page) - the starting page is used as the citation-relevant
            page number, since that's where a reader would look first.
    """

    chunk_index: int
    content: str
    token_count: int
    page_number: int


@dataclass(frozen=True)
class EnrichedChunkRecord:
    """
    A `ChunkRecord` merged with document-level metadata - the output
    of the "Metadata Extraction" pipeline stage, and the final shape
    `DocumentIngestionService.ingest(...)` returns.

    WHY this is a SEPARATE dataclass from `ChunkRecord` rather than
    just adding these fields to `ChunkRecord` directly:
    `ChunkingService` (which produces `ChunkRecord`) has no knowledge
    of - and should have no knowledge of - document-level facts like
    `department` or `upload_date`. Keeping them as two distinct types
    makes that separation of responsibility explicit and enforced by
    the type system: a `ChunkingService` unit test constructing a
    plain `ChunkRecord` simply cannot accidentally smuggle in
    document-level fields it was never given.

    This is the exact shape the upcoming `services/` persistence
    layer consumes to build both a `Chunk` ORM row (see
    `app/database/models/chunk.py`) and its corresponding ChromaDB
    metadata payload - the field names here were chosen to match
    those two destinations directly, requiring no translation layer.
    """

    chunk_index: int
    content: str
    token_count: int
    page_number: int
    document_name: str
    document_type: str
    department: Optional[str]
    equipment_id: Optional[str]
    upload_date: str


@dataclass(frozen=True)
class IngestionResult:
    """
    The complete result of running a document through the full
    ingestion pipeline (Text Extraction -> OCR -> Cleaning -> Chunking
    -> Metadata Extraction), ready to be handed to the embedding and
    persistence stages by the `services/` orchestration layer.

    Attributes:
        total_pages: Total page count of the source document.
        ocr_page_count: How many of those pages required OCR (i.e.
            had no usable native text layer) - surfaced for ingestion
            quality visibility, per `ExtractedDocument.ocr_page_count`.
        chunks: The final, metadata-enriched chunks covering the
            entire document, in order.
    """

    total_pages: int
    ocr_page_count: int
    chunks: List[EnrichedChunkRecord] = field(default_factory=list)
