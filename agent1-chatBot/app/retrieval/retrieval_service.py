"""
app/retrieval/retrieval_service.py

WHY THIS FILE EXISTS
---------------------
This is the ONE service that implements the query pipeline's
Embedding -> Vector Search -> Metadata Filtering -> Cross Encoder
ReRanking stages as a single, orchestrated call. It depends on
`EmbeddingService`, `VectorStoreService`, and
`CrossEncoderRerankerService` - never re-implementing any of their
logic - and its only real job is SEQUENCING them correctly and
deciding when zero results legitimately becomes a
`NoRetrievalResultsError`.

WHY this orchestration lives in its OWN service rather than being
inlined into a future `api/` route handler or a `services/` "query
service" that also handles prompt building and LLM calls: per the
spec's Most Important Requirement, "Retrieval Service" is explicitly
named as one of the reusable capabilities Agent 2/3/4 or a future
orchestrator must be able to depend on independently. A maintenance
agent, for instance, might want ONLY retrieval (find relevant
manuals/procedures) without ever calling Groq at all. Keeping
retrieval fully self-contained and Groq-agnostic is what makes that
possible.
"""

import time
from typing import Any, Dict, List, Optional

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import NoRetrievalResultsError
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.reranker_service import CrossEncoderRerankerService
from app.embeddings.schemas import RerankCandidate, RerankResult
from app.retrieval.vector_store_service import VectorStoreService


def build_metadata_filter(
    department: Optional[str] = None,
    equipment_id: Optional[str] = None,
    document_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Translate the query pipeline's Metadata Filtering stage inputs
    into a ChromaDB `where` clause.

    WHY this is a free function rather than a method on
    `RetrievalService`: filter construction has no dependency on
    ANY service state (no model, no client, no settings) - it is a
    pure function of its inputs. Keeping it standalone makes it
    trivially unit-testable on its own and reusable by anything that
    needs to build the same kind of filter (e.g. a future `api/`
    route validating filter combinations before calling retrieval).

    WHY ChromaDB's `$and` operator is only used when there are 2+
    conditions: ChromaDB rejects a `$and` with fewer than two clauses,
    so this function special-cases 0 and 1 conditions explicitly
    rather than always wrapping in `$and` and hoping ChromaDB accepts
    a degenerate case.

    Args:
        department: Restrict results to chunks tagged with this
            department, or None for no department filter.
        equipment_id: Restrict results to chunks tagged with this
            equipment id, or None for no equipment filter.
        document_type: Restrict results to chunks from this document
            type (see `app.core.constants.DocumentType`), or None.

    Returns:
        A ChromaDB `where` clause dict, or `None` if no filters were
        provided (meaning: search the entire collection).
    """
    conditions: List[Dict[str, Any]] = []
    if department:
        conditions.append({"department": department})
    if equipment_id:
        conditions.append({"equipment_id": equipment_id})
    if document_type:
        conditions.append({"document_type": document_type})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


class RetrievalService(BaseService):
    """
    Orchestrates query embedding, metadata-filtered vector search, and
    cross-encoder reranking into the query pipeline's full retrieval
    stage.
    """

    def __init__(
        self,
        settings: Settings,
        embedding_service: EmbeddingService,
        vector_store_service: VectorStoreService,
        reranker_service: CrossEncoderRerankerService,
    ) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                TOP_K_VECTOR_SEARCH and TOP_K_AFTER_RERANK.
            embedding_service: Shared embedding service (see
                app/embeddings/embedding_service.py) - injected rather
                than constructed here so the SAME instance (and thus
                the SAME loaded model) is reused across the entire
                application, not re-loaded per retrieval call.
            vector_store_service: Shared ChromaDB wrapper.
            reranker_service: Shared cross-encoder reranker.
        """
        super().__init__(settings)
        self.embedding_service = embedding_service
        self.vector_store_service = vector_store_service
        self.reranker_service = reranker_service

    def retrieve(
        self,
        query: str,
        *,
        department: Optional[str] = None,
        equipment_id: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k_vector: Optional[int] = None,
        top_k_rerank: Optional[int] = None,
    ) -> List[RerankResult]:
        """
        Execute the full retrieval stage: embed the query, search
        ChromaDB (optionally metadata-filtered), and rerank the
        candidates.

        Args:
            query: The user's raw question text.
            department: Optional metadata filter.
            equipment_id: Optional metadata filter.
            document_type: Optional metadata filter (see
                `app.core.constants.DocumentType`).
            top_k_vector: Override for `Settings.TOP_K_VECTOR_SEARCH`.
            top_k_rerank: Override for `Settings.TOP_K_AFTER_RERANK`.

        Returns:
            Up to `top_k_rerank` `RerankResult` objects, sorted by
            cross-encoder relevance descending - ready for the
            Context Builder pipeline stage (upcoming `prompts/`
            folder).

        Raises:
            NoRetrievalResultsError: when vector search (after
                metadata filtering) returns zero chunks. Callers
                should catch this specifically to produce the spec's
                exact "No relevant information found in indexed
                documents." response rather than treating it as a
                generic failure.
        """
        effective_top_k_vector = top_k_vector or self.settings.TOP_K_VECTOR_SEARCH
        effective_top_k_rerank = top_k_rerank or self.settings.TOP_K_AFTER_RERANK

        # --- Stage: Query Embedding --------------------------------
        with_timer_start = time.perf_counter()
        query_embedding = self.embedding_service.embed_query(query)
        embedding_ms = (time.perf_counter() - with_timer_start) * 1000

        # --- Stage: Metadata Filtering (filter construction) --------
        where_clause = build_metadata_filter(department, equipment_id, document_type)

        # --- Stage: Vector Search (filter applied here, in ChromaDB) -
        search_start = time.perf_counter()
        vector_results = self.vector_store_service.query(
            query_embedding=query_embedding,
            top_k=effective_top_k_vector,
            where=where_clause,
        )
        search_ms = (time.perf_counter() - search_start) * 1000

        self.logger.bind(stage=PipelineStage.VECTOR_SEARCH.value).info(
            f"Query embedded in {embedding_ms:.1f}ms, vector search returned "
            f"{len(vector_results)} candidate(s) in {search_ms:.1f}ms "
            f"(filters={'yes' if where_clause else 'none'})"
        )

        if not vector_results:
            raise NoRetrievalResultsError(
                stage=PipelineStage.VECTOR_SEARCH,
                details={
                    "query": query,
                    "filters": where_clause,
                    "top_k_vector": effective_top_k_vector,
                },
            )

        # --- Stage: Cross Encoder ReRanking --------------------------
        candidates = [
            RerankCandidate(
                chunk_id=result.chunk_id,
                text=result.text,
                metadata={**result.metadata, "vector_similarity_score": result.similarity_score},
            )
            for result in vector_results
        ]
        rerank_start = time.perf_counter()
        reranked = self.reranker_service.rerank(query, candidates, top_k=effective_top_k_rerank)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

        self.logger.bind(stage=PipelineStage.RERANKING.value).info(
            f"Reranked {len(candidates)} candidate(s) -> {len(reranked)} kept "
            f"in {rerank_ms:.1f}ms"
        )

        # WHY this second empty-check exists even though `vector_results`
        # was already confirmed non-empty above: `top_k_rerank` could in
        # principle be passed as 0 by a caller, which would legitimately
        # produce an empty reranked list from non-empty candidates. This
        # is still "no usable context for the LLM", so it must raise the
        # same error the Context Builder / prompt stage expects to catch.
        if not reranked:
            raise NoRetrievalResultsError(
                "No relevant information found in indexed documents.",
                stage=PipelineStage.RERANKING,
                details={
                    "query": query,
                    "filters": where_clause,
                    "candidate_count": len(candidates),
                    "top_k_rerank": effective_top_k_rerank,
                },
            )

        return reranked

    def health_check(self) -> Dict[str, Any]:
        """
        Aggregates the health of every sub-service this orchestrator
        depends on, so GET /health can report ONE retrieval-pipeline
        status derived from all three underlying components.
        """
        embedding_health = self.embedding_service.health_check()
        vector_store_health = self.vector_store_service.health_check()
        reranker_health = self.reranker_service.health_check()

        all_healthy = (
            embedding_health["healthy"]
            and vector_store_health["healthy"]
            and reranker_health["healthy"]
        )
        return {
            "service": self.service_name,
            "healthy": all_healthy,
            "details": {
                "embedding_service": embedding_health,
                "vector_store_service": vector_store_health,
                "reranker_service": reranker_health,
            },
        }
