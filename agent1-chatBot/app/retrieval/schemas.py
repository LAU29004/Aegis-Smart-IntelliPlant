"""
app/retrieval/schemas.py

WHY THIS FILE EXISTS
---------------------
`VectorSearchResult` is the internal domain object returned by
`VectorStoreService.query` - the raw output of stage one (ANN vector
search) before it is converted into `RerankCandidate` objects (see
`app/embeddings/schemas.py`) for stage two (cross-encoder reranking).

Kept as its own tiny dataclass, separate from `RerankCandidate`,
because it carries fields that are ONLY meaningful at the vector-
search stage (`distance`, the raw ChromaDB metric) and not needed -
or even meaningful - once reranking has happened. Collapsing these
two into one shared class would force every consumer to reason about
fields that may or may not be populated depending on which pipeline
stage produced the object.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class VectorSearchResult:
    """
    One chunk returned by ChromaDB's approximate nearest-neighbor
    search, before reranking.

    Attributes:
        chunk_id: The `Chunk.id` / `chroma_vector_id` this result
            corresponds to.
        text: The chunk's raw content, as originally embedded.
        metadata: The chunk's denormalized metadata payload as stored
            in ChromaDB (document_name, page_number, department,
            equipment_id, document_type, upload_date, document_id).
        distance: The raw distance metric ChromaDB returned for this
            result (lower = more similar, given this service's
            collection is configured with `hnsw:space: cosine`).
        similarity_score: `1 - distance`, i.e. cosine similarity in
            [0, 1] (higher = more similar). Computed once here rather
            than by every caller, so `confidence/` (upcoming folder)
            and `embeddings/`'s `RerankCandidate` conversion both read
            the exact same, consistently-derived number.
    """

    chunk_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    distance: float = 0.0
    similarity_score: float = 0.0
