"""
app/embeddings/schemas.py

WHY THIS FILE EXISTS
---------------------
`RerankCandidate` and `RerankResult` are internal domain objects
passed between `retrieval/` (upcoming folder, which produces
candidates from ChromaDB) and `CrossEncoderRerankerService` below.
They deliberately live in `embeddings/` (not `app/schemas/`) because
`app/schemas/` is reserved for Pydantic API request/response models
validated at the FastAPI boundary - these are plain, immutable
dataclasses used purely in internal service-to-service calls, where
Pydantic's validation overhead buys nothing since both producer and
consumer are trusted first-party code.

WHY `frozen=True` on both: candidates and results flow through a
pipeline stage (reranking) and must not be mutated afterward - e.g.
accidentally re-sorting a `RerankResult` list in place elsewhere in
the pipeline should not be able to also silently corrupt a `score`
field. Immutability makes that class of bug impossible.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RerankCandidate:
    """
    One chunk retrieved from ChromaDB's vector search, about to be
    scored by the cross-encoder against the user's query.

    Attributes:
        chunk_id: The `Chunk.id` (also `chroma_vector_id`) this
            candidate corresponds to - carried through reranking so
            the final `RerankResult` can still be traced back to its
            source row for citation building.
        text: The chunk's raw content, exactly as embedded.
        metadata: The chunk's denormalized filtering/citation fields
            (document_name, page_number, department, equipment_id,
            document_type, upload_date) as produced by the retrieval
            stage - passed through untouched so `CitationBuildError`-
            avoiding citation construction downstream never has to
            re-fetch this from Postgres.
    """

    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RerankResult:
    """
    One `RerankCandidate` after cross-encoder scoring, ready to be
    handed to the Context Builder pipeline stage.

    Attributes:
        chunk_id: Same as the source candidate's `chunk_id`.
        text: Same as the source candidate's `text`.
        score: The cross-encoder's raw relevance score for
            (query, text). NOT yet normalized into the 0-100
            confidence scale - that conversion is the responsibility
            of the `confidence/` module (upcoming folder), which
            deliberately stays decoupled from HOW the score was
            produced.
        metadata: Passed through unchanged from the source candidate.
        original_vector_rank: The candidate's 0-based position in the
            original (pre-rerank) vector search results, retained
            purely for debugging/observability - e.g. logging how much
            reranking actually reordered the list relative to raw
            vector similarity.
    """

    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_vector_rank: Optional[int] = None
