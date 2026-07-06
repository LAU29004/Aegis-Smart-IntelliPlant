"""
app/retrieval/vector_store_service.py

WHY THIS FILE EXISTS
---------------------
Exactly ONE class in this codebase is allowed to import `chromadb`
directly. Every other module that needs to write or search vectors
goes through `VectorStoreService`. This mirrors the same rationale as
`EmbeddingService` being the sole owner of `sentence_transformers`:
centralizing the third-party dependency means a future swap of vector
store technology (e.g. to a managed pgvector or a different ANN
engine) touches exactly one file, and every error path is normalized
into this service's own typed exceptions
(`VectorStoreConnectionError` / `VectorStoreWriteError`) rather than
leaking raw `chromadb` exceptions into `retrieval/`, `ingestion/`, or
`api/`.

WHY embeddings are ALWAYS supplied explicitly by the caller (never
computed by ChromaDB itself via a built-in embedding function): this
service deliberately disables ChromaDB's default embedding function
(which would otherwise lazily download its own ONNX model from the
network on first use). `EmbeddingService` (see `app/embeddings/`) is
the ONE place embeddings are produced in this codebase - ChromaDB
here is used purely as a vector INDEX, never as an embedding
PRODUCER. This is what guarantees ingestion-time and query-time
vectors always come from the identical model.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import VectorStoreConnectionError, VectorStoreWriteError
from app.retrieval.schemas import VectorSearchResult


class _RefuseToEmbed:
    """
    A ChromaDB `EmbeddingFunction` stand-in that must NEVER actually be
    invoked.

    WHY this exists rather than leaving ChromaDB's default embedding
    function in place: this service's entire contract is that
    embeddings are always supplied explicitly by the caller (which
    always means `EmbeddingService`). If a code path is ever
    accidentally introduced that calls `collection.add(...)` or
    `collection.query(...)` WITHOUT explicit embeddings, ChromaDB would
    silently fall back to computing its own - using a completely
    different, un-validated model - and every retrieval from that
    point on would be subtly, confusingly wrong. Raising loudly here
    turns that entire bug class into an immediate, obvious failure at
    the exact moment it would occur, instead of a silent quality
    regression discovered much later.

    WHY `get_config`/`build_from_config` are implemented (in addition
    to `__call__`/`name`): newer ChromaDB versions persist an embedding
    function's config alongside the collection and treat classes
    without these two methods as "legacy", emitting a deprecation
    warning on every collection open. Implementing the full modern
    interface - even though this function has no real config to
    serialize - keeps collection metadata handling on ChromaDB's
    current code path with no warnings, and keeps this class from
    silently becoming unsupported in a future ChromaDB major version.
    """

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A002
        raise RuntimeError(
            "VectorStoreService was invoked without explicit embeddings. "
            "This service never auto-embeds text - all embeddings must "
            "come from app.embeddings.EmbeddingService. This indicates a "
            "programming error in the caller."
        )

    @staticmethod
    def name() -> str:
        # WHY required: newer chromadb versions register embedding
        # functions by name for collection metadata persistence -
        # giving this a stable, self-explanatory name means anyone
        # inspecting the collection's stored config later immediately
        # understands embeddings are intentionally external. WHY
        # `@staticmethod` specifically: chromadb's internal registration
        # machinery calls `EmbeddingFunctionClass.name()` unbound (on the
        # class, not an instance) - matching the exact convention its own
        # built-in embedding functions (e.g. `ONNXMiniLM_L6_V2`) use.
        return "intelliplant-external-embeddings-only"

    def get_config(self) -> dict:
        """No configurable state - this function is a pure refusal stub."""
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "_RefuseToEmbed":
        """Reconstructs from persisted config - trivial, since there is none."""
        return _RefuseToEmbed()

    def is_legacy(self) -> bool:
        """WHY False: signals to ChromaDB this class fully implements the
        modern EmbeddingFunction interface (get_config/build_from_config/
        default_space/supported_spaces), avoiding the legacy-embedding-
        function deprecation path entirely."""
        return False

    def default_space(self) -> str:
        """WHY "cosine": matches the `hnsw:space: cosine` this service's
        collection is always configured with (see `_get_collection`) -
        EmbeddingService's L2-normalized vectors are designed for cosine
        similarity."""
        return "cosine"

    def supported_spaces(self) -> List[str]:
        return ["cosine"]


def _default_client_factory(settings: Settings) -> Any:
    """
    Production ChromaDB client factory - constructs a real persistent
    client. Import kept local for the same reason as the embedding
    services' default loaders: avoid the import cost for code paths
    (or tests) that inject a fake client and never need the real
    `chromadb` package touched at all.
    """
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    return chromadb.PersistentClient(
        path=settings.CHROMA_PERSIST_DIRECTORY,
        settings=ChromaSettings(anonymized_telemetry=False),
        # WHY anonymized_telemetry=False: this is an internal
        # industrial knowledge platform - document content and
        # equipment identifiers are exactly the kind of data that
        # should never be phoned home anywhere, even as anonymized
        # usage telemetry.
    )


class VectorStoreService(BaseService):
    """
    Wraps a ChromaDB persistent collection for chunk embedding storage
    and approximate nearest-neighbor similarity search.
    """

    def __init__(
        self,
        settings: Settings,
        client_factory: Optional[Callable[[Settings], Any]] = None,
    ) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                CHROMA_PERSIST_DIRECTORY and CHROMA_COLLECTION_NAME.
            client_factory: Optional factory `(settings) -> chromadb
                client-like object`. Defaults to
                `_default_client_factory`. Tests inject an in-memory
                `chromadb.EphemeralClient` (still real ChromaDB, no
                network required) to validate this service's logic
                against genuine ChromaDB query/filter semantics
                without touching disk persistence.
        """
        super().__init__(settings)
        self._client_factory = client_factory or _default_client_factory
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None

    def warm_up(self) -> None:
        """Force the client and collection to initialize now - called
        from application startup, mirroring EmbeddingService.warm_up."""
        self._get_collection()

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection

        try:
            self._client = self._client_factory(self.settings)
            self._collection = self._client.get_or_create_collection(
                name=self.settings.CHROMA_COLLECTION_NAME,
                embedding_function=_RefuseToEmbed(),
                metadata={"hnsw:space": "cosine"},
                # WHY cosine explicitly: this must match the similarity
                # semantics EmbeddingService's L2-normalized vectors are
                # designed for, and must match what `confidence/`
                # (upcoming folder) assumes when converting distance to
                # a 0-100 confidence score.
            )
        except Exception as exc:
            raise VectorStoreConnectionError(
                "Could not connect to or open the ChromaDB collection.",
                stage=PipelineStage.VECTOR_STORE_WRITE,
                details={
                    "persist_directory": self.settings.CHROMA_PERSIST_DIRECTORY,
                    "collection_name": self.settings.CHROMA_COLLECTION_NAME,
                },
                original_exception=exc,
            ) from exc

        self.logger.bind(stage=PipelineStage.VECTOR_STORE_WRITE.value).info(
            f"ChromaDB collection '{self.settings.CHROMA_COLLECTION_NAME}' ready "
            f"at '{self.settings.CHROMA_PERSIST_DIRECTORY}'"
        )
        return self._collection

    def add_chunks(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
    ) -> None:
        """
        Write a batch of embedded chunks into the collection.

        WHY all four sequences are required to be the same length,
        validated up front: ChromaDB's own error for a length
        mismatch is a fairly opaque internal assertion. Validating
        here produces a clear, typed `VectorStoreWriteError` that
        names exactly which lengths disagreed, which matters a lot
        when this is called with hundreds of chunks from a single
        document's ingestion batch.

        Args:
            ids: Chunk UUIDs (as strings) - MUST equal each chunk's
                `Chunk.id` / `chroma_vector_id` in Postgres, so the two
                stores stay joinable by this shared key.
            embeddings: One embedding vector per id, from
                `EmbeddingService.embed_documents`.
            documents: One raw chunk text per id.
            metadatas: One metadata dict per id (document_name,
                page_number, department, equipment_id, document_type,
                upload_date, document_id).
        """
        lengths = {
            "ids": len(ids),
            "embeddings": len(embeddings),
            "documents": len(documents),
            "metadatas": len(metadatas),
        }
        if len(set(lengths.values())) != 1:
            raise VectorStoreWriteError(
                "ids/embeddings/documents/metadatas must all have the same "
                "length.",
                stage=PipelineStage.VECTOR_STORE_WRITE,
                details=lengths,
            )
        if not ids:
            raise VectorStoreWriteError(
                "Cannot add an empty batch of chunks to the vector store.",
                stage=PipelineStage.VECTOR_STORE_WRITE,
            )

        collection = self._get_collection()
        # WHY metadata values are sanitized here before ever reaching
        # ChromaDB: ChromaDB's metadata values must be str/int/float/bool
        # - it rejects `None` outright (e.g. a chunk whose parent
        # document has no `equipment_id`). Rather than pushing this
        # ChromaDB-specific constraint out onto every caller (ingestion
        # code building metadata dicts would otherwise need to
        # remember to omit None fields itself), this service - the
        # ONE place that owns the ChromaDB contract - strips None
        # values immediately before the write. A field simply absent
        # from metadata (rather than present with value None) is
        # already handled correctly everywhere metadata is read
        # (`dict.get(...)` calls throughout this codebase).
        sanitized_metadatas = [
            {k: v for k, v in metadata.items() if v is not None}
            for metadata in metadatas
        ]
        start = time.perf_counter()
        try:
            collection.add(
                ids=list(ids),
                embeddings=[list(e) for e in embeddings],
                documents=list(documents),
                metadatas=sanitized_metadatas,
            )
        except Exception as exc:
            raise VectorStoreWriteError(
                "Failed to write chunk batch to ChromaDB.",
                stage=PipelineStage.VECTOR_STORE_WRITE,
                details={"batch_size": len(ids)},
                original_exception=exc,
            ) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.logger.bind(stage=PipelineStage.VECTOR_STORE_WRITE.value).info(
            f"Wrote {len(ids)} chunk(s) to ChromaDB in {elapsed_ms:.1f}ms"
        )

    def query(
        self,
        query_embedding: Sequence[float],
        top_k: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Run an approximate nearest-neighbor search against the
        collection, optionally constrained by a metadata filter.

        Args:
            query_embedding: The user's query vector, from
                `EmbeddingService.embed_query`.
            top_k: Number of nearest neighbors to return
                (`Settings.TOP_K_VECTOR_SEARCH` at the call site).
            where: Optional ChromaDB metadata filter clause (e.g.
                `{"department": "Maintenance"}` or a `$and`/`$or`
                compound clause) implementing the pipeline's Metadata
                Filtering stage.

        Returns:
            Up to `top_k` `VectorSearchResult` objects, ordered by
            similarity descending (nearest first). Returns an EMPTY
            list (never raises) when there are zero matches - it is
            the CALLER's (`RetrievalService`) responsibility to decide
            whether an empty result set should become a
            `NoRetrievalResultsError`, keeping this method a pure,
            always-safe reflection of what ChromaDB actually found.
        """
        collection = self._get_collection()
        start = time.perf_counter()
        try:
            raw_results = collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=top_k,
                where=where if where else None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreConnectionError(
                "ChromaDB query failed.",
                stage=PipelineStage.VECTOR_SEARCH,
                details={"top_k": top_k, "where": where},
                original_exception=exc,
            ) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        # ChromaDB's query() returns each field as a list-of-lists (one
        # inner list per query embedding submitted). We only ever submit
        # exactly one query embedding at a time, so we always read index 0.
        ids = raw_results.get("ids", [[]])[0]
        documents = raw_results.get("documents", [[]])[0]
        metadatas = raw_results.get("metadatas", [[]])[0]
        distances = raw_results.get("distances", [[]])[0]

        results = [
            VectorSearchResult(
                chunk_id=chunk_id,
                text=text or "",
                metadata=metadata or {},
                distance=float(distance),
                # WHY `1 - distance`: this collection is configured with
                # `hnsw:space: cosine`, under which ChromaDB's "distance"
                # is `1 - cosine_similarity`. Inverting it back here
                # means every consumer of `VectorSearchResult` works with
                # an intuitive "higher is better" similarity score
                # instead of needing to remember which metric space a
                # raw distance came from.
                similarity_score=1.0 - float(distance),
            )
            for chunk_id, text, metadata, distance in zip(
                ids, documents, metadatas, distances
            )
        ]

        self.logger.bind(stage=PipelineStage.VECTOR_SEARCH.value).debug(
            f"Vector search returned {len(results)} result(s) "
            f"(top_k={top_k}, filtered={where is not None}) in {elapsed_ms:.1f}ms"
        )
        return results

    def delete_by_document_id(self, document_id: str) -> int:
        """
        Delete every chunk vector belonging to a given document -
        called by the service layer's document-deletion flow
        (DELETE /document/{id}) to keep ChromaDB in sync with the
        cascade-deleted `Chunk` rows in Postgres, since SQLAlchemy's
        cascade cannot reach a separate store like ChromaDB.

        Returns:
            The number of vectors deleted, for logging/verification.
        """
        collection = self._get_collection()
        try:
            existing = collection.get(where={"document_id": document_id})
            count = len(existing.get("ids", []))
            if count:
                collection.delete(where={"document_id": document_id})
        except Exception as exc:
            raise VectorStoreWriteError(
                "Failed to delete document chunks from ChromaDB.",
                stage=PipelineStage.VECTOR_STORE_WRITE,
                details={"document_id": document_id},
                original_exception=exc,
            ) from exc

        self.logger.bind(stage=PipelineStage.VECTOR_STORE_WRITE.value).info(
            f"Deleted {count} chunk vector(s) for document_id={document_id}"
        )
        return count

    def health_check(self) -> Dict[str, Any]:
        """
        Verifies the collection is reachable and reports its current
        vector count.
        """
        try:
            collection = self._get_collection()
            count = collection.count()
            return {
                "service": self.service_name,
                "healthy": True,
                "details": {
                    "collection_name": self.settings.CHROMA_COLLECTION_NAME,
                    "vector_count": count,
                },
            }
        except VectorStoreConnectionError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
