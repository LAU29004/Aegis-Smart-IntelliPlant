"""
app/citations/schemas.py

WHY THIS FILE EXISTS
---------------------
The spec's JSON response has TWO distinct source-related fields:
`citations` (the specific sources the LLM actually referenced inline
via `[n]` markers in its answer) and `related_documents` (the broader
set of documents retrieval surfaced as relevant, regardless of
whether the LLM happened to cite every one of them). These are
genuinely different pieces of information for the API consumer - a
frontend might render `citations` as inline footnote links within the
answer text, and `related_documents` as a separate "see also" list -
so they get two distinct dataclasses here rather than overloading one
shape for both purposes.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Citation:
    """
    One source the LLM's answer actually cited via a `[n]` marker,
    resolved back to its full source metadata.

    WHY `number` (not `index`, matching `SourceReference.index`): this
    is deliberately renamed at this boundary - `index` in
    `SourceReference` is an internal pipeline detail (the position
    used to build the numbered context block), while `number` here is
    the public, API-facing field name representing exactly the digit
    that appears in the answer text's `[n]` marker. They happen to
    hold the same value, but naming them differently makes clear this
    is now a response schema field, not a re-export of the internal
    building-block type.
    """

    number: int
    chunk_id: str
    document_name: str
    page_number: Optional[int]
    department: Optional[str]
    equipment_id: Optional[str]
    relevance_score: float


@dataclass(frozen=True)
class RelatedDocument:
    """
    One document retrieval surfaced as relevant to the query, with all
    of its contributing chunks' page numbers aggregated - populates
    the spec's `related_documents` response field.

    WHY page numbers are aggregated into a list per document rather
    than keeping one `RelatedDocument` per chunk: if 3 of the 5
    reranked chunks all came from the same manual (different pages),
    an API consumer wants ONE entry for that manual listing every
    relevant page, not 3 near-duplicate entries - this is a genuine
    "which documents matter here" summary, distinct from the
    chunk-level detail `citations` already provides.
    """

    document_name: str
    department: Optional[str]
    equipment_id: Optional[str]
    page_numbers: List[int] = field(default_factory=list)
    chunk_count: int = 0
