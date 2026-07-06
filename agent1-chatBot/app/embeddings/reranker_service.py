"""
app/embeddings/reranker_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Cross Encoder ReRanking" stage of the query pipeline:
takes the TOP_K_VECTOR_SEARCH (15) candidates returned by the bi-
encoder vector search, scores each (query, chunk_text) pair jointly
with a cross-encoder, and returns the TOP_K_AFTER_RERANK (5) highest-
scoring ones. WHY this two-stage design instead of just using the
cross-encoder for everything: a cross-encoder must jointly process
every (query, candidate) pair through the full transformer - far too
slow to run against an entire document collection on every query. The
bi-encoder's fast approximate nearest-neighbor search narrows the
field to a small candidate set FIRST, and only that small set pays the
cross-encoder's higher accuracy/higher latency cost.

Like `EmbeddingService`, the underlying model is lazily loaded and its
backend is injectable via `model_loader`, for the same reasons: cheap
construction, model loading deferred to an explicit `warm_up()` call
at application startup, and full unit-testability without a real
model download.
"""

import time
from typing import Callable, List, Optional, Protocol, Sequence

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import RerankingError
from app.embeddings.schemas import RerankCandidate, RerankResult
from typing import Any

class _CrossEncoderModel(Protocol):
    """
    Structural type describing exactly the subset of
    `sentence_transformers.CrossEncoder`'s interface this service
    relies on. See `embedding_service.py::_EncoderModel` for the full
    rationale behind using a Protocol here.
    """

    def predict(self, sentence_pairs: List[tuple]) -> "Any":  # noqa: F821
        ...


def _default_model_loader(model_name: str) -> _CrossEncoderModel:
    """
    Production model loader - imports and constructs a real
    `sentence_transformers.CrossEncoder`. Import kept local for the
    same reason as `embedding_service.py`'s default loader: avoid
    paying the heavy `sentence-transformers`/`torch` import cost for
    code paths (or tests) that never actually need a real model.
    """
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name)


class CrossEncoderRerankerService(BaseService):
    """
    Wraps a Sentence-Transformers cross-encoder to re-score and
    re-order vector-search candidates for a given query.
    """

    def __init__(
        self,
        settings: Settings,
        model_loader: Optional[Callable[[str], _CrossEncoderModel]] = None,
    ) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                CROSS_ENCODER_MODEL_NAME and TOP_K_AFTER_RERANK are
                used by this service.
            model_loader: Optional factory `(model_name) -> encoder`.
                Defaults to `_default_model_loader`. Tests inject a
                fake loader to avoid network calls / heavy imports.
        """
        super().__init__(settings)
        self._model_loader = model_loader or _default_model_loader
        self._model: Optional[_CrossEncoderModel] = None

    def warm_up(self) -> None:
        """Force the cross-encoder to load now - see EmbeddingService.warm_up
        for the full rationale (called from app startup, not lazily on a
        user's first request)."""
        self._get_model()

    def _get_model(self) -> _CrossEncoderModel:
        if self._model is not None:
            return self._model

        model_name = self.settings.CROSS_ENCODER_MODEL_NAME
        self.logger.bind(stage=PipelineStage.RERANKING.value).info(
            f"Loading cross-encoder reranker model '{model_name}'..."
        )
        try:
            self._model = self._model_loader(model_name)
        except Exception as exc:
            raise RerankingError(
                f"Failed to load cross-encoder model '{model_name}'.",
                stage=PipelineStage.RERANKING,
                details={"model_name": model_name},
                original_exception=exc,
            ) from exc

        self.logger.bind(stage=PipelineStage.RERANKING.value).info(
            f"Cross-encoder model '{model_name}' loaded"
        )
        return self._model

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        top_k: Optional[int] = None,
    ) -> List[RerankResult]:
        """
        Score every candidate against the query and return the
        highest-scoring `top_k` (default: `Settings.TOP_K_AFTER_RERANK`),
        sorted by score descending.

        WHY this method deliberately does NOT raise when `candidates`
        is empty (unlike `EmbeddingService._encode`, which DOES reject
        empty input): an empty candidate list reaching this stage is
        not itself an error condition here - it's the retrieval
        stage's job (upcoming `retrieval/` folder) to raise
        `NoRetrievalResultsError` BEFORE reranking is ever invoked.
        This method simply returns an empty result list, keeping it a
        pure, always-safe function of its input rather than
        second-guessing an earlier pipeline stage's decision.

        Args:
            query: The user's original question (unembedded raw text
                - the cross-encoder consumes text pairs directly, not
                pre-computed vectors).
            candidates: Chunks to score, typically the TOP_K_VECTOR_SEARCH
                results from the retrieval stage.
            top_k: Override for how many results to keep. Defaults to
                `Settings.TOP_K_AFTER_RERANK` when not provided.

        Returns:
            Up to `top_k` `RerankResult` objects, sorted by score
            descending.
        """
        if not candidates:
            return []

        effective_top_k = top_k if top_k is not None else self.settings.TOP_K_AFTER_RERANK

        model = self._get_model()
        pairs = [(query, candidate.text) for candidate in candidates]

        start = time.perf_counter()
        try:
            raw_scores = model.predict(pairs)
        except Exception as exc:
            raise RerankingError(
                "Cross-encoder failed to score query-candidate pairs.",
                stage=PipelineStage.RERANKING,
                details={"candidate_count": len(candidates)},
                original_exception=exc,
            ) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        if len(raw_scores) != len(candidates):
            # WHY this defensive check matters: a `model_loader` (real
            # OR fake, in tests) that returns a mismatched score count
            # would otherwise cause `zip` below to silently truncate
            # results without any indication something is wrong - far
            # better to fail loudly here than serve a subtly incomplete
            # reranked list to the LLM.
            raise RerankingError(
                "Cross-encoder returned a different number of scores than "
                "candidates provided.",
                stage=PipelineStage.RERANKING,
                details={
                    "candidate_count": len(candidates),
                    "score_count": len(raw_scores),
                },
            )

        results = [
            RerankResult(
                chunk_id=candidate.chunk_id,
                text=candidate.text,
                score=float(score),
                metadata=candidate.metadata,
                original_vector_rank=original_rank,
            )
            for original_rank, (candidate, score) in enumerate(zip(candidates, raw_scores))
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        top_results = results[:effective_top_k]

        self.logger.bind(stage=PipelineStage.RERANKING.value).debug(
            f"Reranked {len(candidates)} candidate(s) -> kept top "
            f"{len(top_results)} in {elapsed_ms:.1f}ms"
        )
        return top_results

    def health_check(self) -> dict:
        """
        Verifies the cross-encoder can actually score a trivial
        (query, candidate) pair, end to end - same rationale as
        `EmbeddingService.health_check`: reflect real, current
        capability rather than just "was `_model` ever set".
        """
        try:
            start = time.perf_counter()
            probe_candidate = RerankCandidate(chunk_id="health-check", text="probe text")
            self.rerank("health check probe", [probe_candidate], top_k=1)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "service": self.service_name,
                "healthy": True,
                "details": {
                    "model_name": self.settings.CROSS_ENCODER_MODEL_NAME,
                    "probe_latency_ms": round(elapsed_ms, 2),
                },
            }
        except RerankingError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
