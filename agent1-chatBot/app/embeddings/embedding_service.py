"""
app/embeddings/embedding_service.py

WHY THIS FILE EXISTS
---------------------
Exactly ONE class in this entire codebase is allowed to call
`sentence_transformers.SentenceTransformer(...).encode(...)`. Both the
ingestion pipeline (embedding chunks before writing to ChromaDB) and
the query pipeline (embedding the user's question before vector
search) go through this SAME `EmbeddingService` instance. This is the
single most important guarantee for retrieval quality: if ingestion
and query embedding ever used two different model instances - even of
the nominally "same" model - a subtle version/config mismatch could
silently degrade vector similarity for every single query. Routing
both through one service, backed by one `Settings.EMBEDDING_MODEL_NAME`,
makes that class of bug structurally impossible.

WHY the underlying model is lazily loaded (not loaded in `__init__`):
loading a transformer model is a slow, memory-heavy operation (real
deployments will want this to happen once at application STARTUP, not
on every dependency-injected instantiation within a request). Lazy
loading with a cached instance variable means `EmbeddingService` can
be constructed cheaply and repeatedly (e.g. in tests) while the
actual model load happens exactly once, on first real use - and
`app/main.py`'s startup event (upcoming `api/` folder) is expected to
call `.warm_up()` explicitly to force that load to happen up front,
rather than on a user's first request.

WHY the model backend is injectable via `model_loader`: this is what
makes the service's BATCHING, ERROR HANDLING, and DIMENSION VALIDATION
logic fully unit-testable without downloading real model weights or
requiring network access - a test can inject a small fake object
exposing the same `.encode(...)` signature and verify this service's
own logic in isolation.
"""

import time
from typing import Callable, List, Optional, Protocol

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import EmbeddingGenerationError


class _EncoderModel(Protocol):
    """
    Structural type describing exactly the subset of
    `sentence_transformers.SentenceTransformer`'s interface this
    service relies on.

    WHY a `Protocol` instead of importing `SentenceTransformer` as the
    type hint directly: it decouples this service's public contract
    from the specific third-party class, which is what allows tests
    (and, in principle, a future swap to a different embedding
    backend) to substitute ANY object satisfying this shape via
    `model_loader`, without subclassing or monkeypatching the real
    `sentence_transformers` package.
    """

    def encode(
        self,
        sentences: List[str],
        batch_size: int,
        normalize_embeddings: bool,
        show_progress_bar: bool,
    ) -> "Any":  # noqa: F821 - returned as a numpy ndarray by the real model
        ...


def _default_model_loader(model_name: str) -> _EncoderModel:
    """
    Production model loader - imports and constructs a real
    `sentence_transformers.SentenceTransformer`.

    WHY the import is INSIDE this function rather than at module top
    level: `sentence-transformers` (and its `torch` dependency) is a
    heavy import. Keeping it local means code that only needs
    `EmbeddingService`'s TYPES (e.g. `retrieval/` importing this
    module just for type hints, or tests injecting a fake loader)
    never pays that import cost unless a real model is actually
    requested.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class EmbeddingService(BaseService):
    """
    Wraps a Sentence-Transformers bi-encoder to produce normalized
    embedding vectors for both document chunks (ingestion) and user
    queries (retrieval).

    WHY embeddings are L2-normalized (`normalize_embeddings=True`):
    ChromaDB's default similarity metric assumes normalized vectors
    for cosine-similarity search to behave correctly and for
    similarity scores to land in a predictable [0, 1] (or [-1, 1])
    range - which the `confidence/` module (upcoming folder) depends
    on to convert similarity into a 0-100 confidence score.
    """

    def __init__(
        self,
        settings: Settings,
        model_loader: Optional[Callable[[str], _EncoderModel]] = None,
    ) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION, and
                EMBEDDING_BATCH_SIZE are used by this service.
            model_loader: Optional factory `(model_name) -> encoder`.
                Defaults to `_default_model_loader`, which constructs
                a real `SentenceTransformer`. Tests inject a fake
                loader here to avoid network calls / heavy imports.
        """
        super().__init__(settings)
        self._model_loader = model_loader or _default_model_loader
        self._model: Optional[_EncoderModel] = None

    def warm_up(self) -> None:
        """
        Force the underlying model to load NOW rather than lazily on
        first use.

        WHY this is a separate public method rather than just relying
        on lazy loading everywhere: `app/main.py`'s startup event
        (upcoming `api/` folder) calls this explicitly so that model
        loading latency (which can be several seconds) happens ONCE
        during container startup / readiness-probe delay, not on an
        unlucky first user's request.
        """
        self._get_model()

    def _get_model(self) -> _EncoderModel:
        """
        Return the cached model instance, loading and validating it
        on first call.

        WHY dimension validation happens HERE, right after load,
        rather than being trusted from config: `EMBEDDING_DIMENSION`
        in settings is a human-maintained value. If someone changes
        `EMBEDDING_MODEL_NAME` in `.env` without also updating
        `EMBEDDING_DIMENSION`, every downstream ChromaDB write would
        silently produce a dimension mismatch that only surfaces as a
        confusing vector-store error much later. Failing loudly here,
        at the moment the model is first loaded, catches that
        misconfiguration immediately and attributes it to the right
        cause.
        """
        if self._model is not None:
            return self._model

        model_name = self.settings.EMBEDDING_MODEL_NAME
        self.logger.bind(stage=PipelineStage.DOCUMENT_EMBEDDING.value).info(
            f"Loading embedding model '{model_name}'..."
        )
        try:
            model = self._model_loader(model_name)
        except Exception as exc:
            raise EmbeddingGenerationError(
                f"Failed to load embedding model '{model_name}'.",
                stage=PipelineStage.DOCUMENT_EMBEDDING,
                details={"model_name": model_name},
                original_exception=exc,
            ) from exc

        # Validate the loaded model actually produces vectors of the
        # dimension configured in Settings, using a cheap throwaway
        # encode call - see docstring above for why this matters.
        try:
            probe_vector = model.encode(
                ["dimension probe"],
                batch_size=1,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            actual_dimension = len(probe_vector[0])
        except Exception as exc:
            raise EmbeddingGenerationError(
                f"Embedding model '{model_name}' loaded but failed to "
                f"encode a probe sentence.",
                stage=PipelineStage.DOCUMENT_EMBEDDING,
                details={"model_name": model_name},
                original_exception=exc,
            ) from exc

        expected_dimension = self.settings.EMBEDDING_DIMENSION
        if actual_dimension != expected_dimension:
            raise EmbeddingGenerationError(
                f"Embedding model '{model_name}' produced vectors of "
                f"dimension {actual_dimension}, but EMBEDDING_DIMENSION "
                f"is configured as {expected_dimension}. Update the "
                f"EMBEDDING_DIMENSION setting to match the model, or "
                f"re-index the ChromaDB collection if the model changed.",
                stage=PipelineStage.DOCUMENT_EMBEDDING,
                details={
                    "model_name": model_name,
                    "actual_dimension": actual_dimension,
                    "expected_dimension": expected_dimension,
                },
            )

        self._model = model
        self.logger.bind(stage=PipelineStage.DOCUMENT_EMBEDDING.value).info(
            f"Embedding model '{model_name}' loaded and validated "
            f"(dimension={actual_dimension})"
        )
        return self._model

    def _encode(
        self, texts: List[str], *, stage: PipelineStage
    ) -> List[List[float]]:
        """
        Shared implementation behind `embed_documents` and
        `embed_query` - encodes a batch of texts and returns plain
        Python `List[List[float]]` (never a raw numpy array), so
        every downstream consumer (ChromaDB writes, JSON serialization
        for logging) never needs to know or care that numpy was
        involved at all.

        WHY batching is handled here (respecting
        `EMBEDDING_BATCH_SIZE`) rather than passing the whole `texts`
        list straight to `model.encode` and letting sentence-
        transformers batch internally: `SentenceTransformer.encode`
        DOES already batch internally when given a `batch_size`
        argument - we pass it through explicitly rather than
        re-implementing batching ourselves, but this method remains
        the one seam where batch size is enforced from `Settings`
        rather than an arbitrary default, and where empty/invalid
        input is rejected before ever reaching the model.
        """
        if not texts:
            raise EmbeddingGenerationError(
                "Cannot embed an empty list of texts.",
                stage=stage,
            )
        cleaned = [t for t in texts if t and t.strip()]
        if not cleaned:
            raise EmbeddingGenerationError(
                "All provided texts were empty or whitespace-only after "
                "cleaning; nothing to embed.",
                stage=stage,
                details={"input_count": len(texts)},
            )

        model = self._get_model()
        start = time.perf_counter()
        try:
            vectors = model.encode(
                cleaned,
                batch_size=self.settings.EMBEDDING_BATCH_SIZE,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingGenerationError(
                "Embedding model failed to encode the provided text batch.",
                stage=stage,
                details={"batch_size": len(cleaned)},
                original_exception=exc,
            ) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.logger.bind(stage=stage.value).debug(
            f"Embedded {len(cleaned)} text(s) in {elapsed_ms:.1f}ms"
        )
        # WHY `[list(v) for v in vectors]` rather than `vectors.tolist()`:
        # this works identically whether `vectors` is a real numpy
        # ndarray (production) or a plain list-of-lists returned by a
        # test's fake model_loader - keeping the service agnostic to
        # numpy specifically at this boundary.
        return [[float(x) for x in vector] for vector in vectors]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of document CHUNK texts during ingestion.

        WHY a distinctly-named method from `embed_query` even though
        the implementation is identical today: some sentence-
        transformer models (e.g. instruction-tuned retrieval models)
        require different prefixes/instructions for documents vs.
        queries to perform well. Keeping these as separate call sites
        NOW means adding that asymmetry later is a change to ONE
        method, not a hunt through every call site in `ingestion/` to
        figure out which calls were "really" query embeddings.
        """
        return self._encode(texts, stage=PipelineStage.DOCUMENT_EMBEDDING)

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single user query for vector search.

        Returns:
            A single embedding vector (not a batch) - the common case
            for the query pipeline, which embeds exactly one question
            per request.
        """
        return self._encode([query], stage=PipelineStage.QUERY_EMBEDDING)[0]

    def health_check(self) -> dict:
        """
        Verifies the embedding model can actually be loaded and used
        by encoding a short probe string, end to end.

        WHY this is more thorough than just checking `self._model is
        not None`: a model that failed to load would leave `_model`
        as `None` forever without this health check ever attempting
        (and thus ever reporting) that failure - GET /health should
        reflect the CURRENT real capability of the service, not just
        whether a previous call happened to succeed.
        """
        try:
            start = time.perf_counter()
            vector = self.embed_query("health check probe")
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "service": self.service_name,
                "healthy": True,
                "details": {
                    "model_name": self.settings.EMBEDDING_MODEL_NAME,
                    "embedding_dimension": len(vector),
                    "probe_latency_ms": round(elapsed_ms, 2),
                },
            }
        except EmbeddingGenerationError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
