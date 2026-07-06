"""
app/embeddings package.

WHY a dedicated `embeddings` package: both the bi-encoder (semantic
similarity search) and the cross-encoder (precise reranking) are
"embedding-adjacent" ML models with similar lazy-loading, health-
check, and error-handling needs, but distinct responsibilities and
distinct underlying model architectures. Grouping them together here
(rather than splitting into `embeddings/` and a separate `reranking/`
folder) reflects that both are internal, model-backed building blocks
consumed by `retrieval/` (upcoming folder) - `retrieval/` is where the
actual VECTOR SEARCH and ORCHESTRATION of these two services into the
two-stage retrieval pipeline lives.

Everything below is exported from here so `retrieval/`, `services/`,
and `api/` never need to import from the individual submodules
directly - `embeddings/` is one clean public surface.
"""

from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.reranker_service import CrossEncoderRerankerService
from app.embeddings.schemas import RerankCandidate, RerankResult

__all__ = [
    "EmbeddingService",
    "CrossEncoderRerankerService",
    "RerankCandidate",
    "RerankResult",
]
