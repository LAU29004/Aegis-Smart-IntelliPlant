"""
app/retrieval package.

WHY a dedicated `retrieval` package: this is where the ChromaDB-
specific vector store logic (`VectorStoreService`) and the pipeline
orchestration that combines it with `embeddings/`'s two model
services (`RetrievalService`) both live. `services/` and `api/`
(upcoming folders) depend on `RetrievalService` as their single entry
point into "find relevant chunks for this query" - they never talk to
`VectorStoreService` or the embedding/reranker services directly for
retrieval purposes, keeping the two-stage retrieval algorithm defined
in exactly one place.
"""

from app.retrieval.retrieval_service import RetrievalService, build_metadata_filter
from app.retrieval.schemas import VectorSearchResult
from app.retrieval.vector_store_service import VectorStoreService

__all__ = [
    "RetrievalService",
    "build_metadata_filter",
    "VectorSearchResult",
    "VectorStoreService",
]
