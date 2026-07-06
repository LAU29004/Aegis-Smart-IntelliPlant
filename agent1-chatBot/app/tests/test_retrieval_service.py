"""
app/tests/test_retrieval_service.py

Unit tests for `app.retrieval.retrieval_service.RetrievalService` -
the query embedding -> metadata-filtered vector search -> reranking
orchestrator, per the spec's explicit "Generate unit tests for ...
Retriever" requirement.

WHY A REAL (EPHEMERAL, IN-MEMORY) CHROMADB INSTANCE IS USED
------------------------------------------------------------------
`chromadb.EphemeralClient()` is genuine ChromaDB, just backed by
memory instead of disk - no network access required, no test-polluting
files left on disk, but real ANN search semantics and real metadata
filtering behavior are exercised, which a hand-rolled fake vector
store could easily get subtly wrong (e.g. `$and` filter syntax).
"""

import chromadb
import pytest

from app.core.exceptions import NoRetrievalResultsError
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.reranker_service import CrossEncoderRerankerService
from app.retrieval.retrieval_service import RetrievalService, build_metadata_filter
from app.retrieval.vector_store_service import VectorStoreService


@pytest.fixture
def vector_store_service(settings) -> VectorStoreService:
    return VectorStoreService(settings, client_factory=lambda s: chromadb.EphemeralClient())


@pytest.fixture
def embedding_service(settings, fake_encoder_loader) -> EmbeddingService:
    return EmbeddingService(settings, model_loader=fake_encoder_loader)


@pytest.fixture
def reranker_service(settings, fake_cross_encoder_loader) -> CrossEncoderRerankerService:
    return CrossEncoderRerankerService(settings, model_loader=fake_cross_encoder_loader)


@pytest.fixture
def retrieval_service(settings, embedding_service, vector_store_service, reranker_service) -> RetrievalService:
    return RetrievalService(settings, embedding_service, vector_store_service, reranker_service)


@pytest.fixture
def seeded_vector_store(embedding_service, vector_store_service):
    """Populates the vector store with a small, known set of chunks for retrieval tests."""
    chunk_texts = [
        "Replace the pump seal every 6 months to prevent leakage.",
        "Wear safety goggles when operating the grinder.",
        "Pump seal maintenance interval and replacement schedule details.",
        "Fire extinguisher inspection checklist for warehouse zone B.",
    ]
    metadatas = [
        {"document_id": "doc-1", "document_name": "Pump Manual.pdf", "page_number": 3,
         "department": "Maintenance", "equipment_id": "PUMP-101", "document_type": "pdf"},
        {"document_id": "doc-2", "document_name": "Safety Handbook.pdf", "page_number": 12,
         "department": "Safety", "document_type": "pdf"},
        {"document_id": "doc-1", "document_name": "Pump Manual.pdf", "page_number": 4,
         "department": "Maintenance", "equipment_id": "PUMP-101", "document_type": "pdf"},
        {"document_id": "doc-3", "document_name": "Fire Safety.pdf", "page_number": 1,
         "department": "Safety", "document_type": "pdf"},
    ]
    ids = [f"chunk-{i}" for i in range(len(chunk_texts))]
    embeddings = embedding_service.embed_documents(chunk_texts)
    vector_store_service.add_chunks(ids=ids, embeddings=embeddings, documents=chunk_texts, metadatas=metadatas)
    return ids


class TestBuildMetadataFilter:
    def test_no_filters_returns_none(self):
        assert build_metadata_filter() is None

    def test_single_filter_returns_bare_condition(self):
        result = build_metadata_filter(department="Maintenance")
        assert result == {"department": "Maintenance"}

    def test_multiple_filters_use_and_operator(self):
        result = build_metadata_filter(department="Maintenance", equipment_id="PUMP-101")
        assert result == {"$and": [{"department": "Maintenance"}, {"equipment_id": "PUMP-101"}]}

    def test_three_filters_all_combined(self):
        result = build_metadata_filter(department="Maintenance", equipment_id="PUMP-101", document_type="pdf")
        assert result["$and"] and len(result["$and"]) == 3


class TestRetrieve:
    def test_unfiltered_retrieval_ranks_most_relevant_chunk_first(self, retrieval_service, seeded_vector_store):
        results = retrieval_service.retrieve("pump seal replacement schedule")
        assert results[0].chunk_id in ("chunk-0", "chunk-2")
        assert results[0].score >= results[-1].score

    def test_department_filter_restricts_results_to_matching_department(self, retrieval_service, seeded_vector_store):
        results = retrieval_service.retrieve("pump seal replacement schedule", department="Safety")
        assert len(results) > 0
        assert all(r.metadata.get("department") == "Safety" for r in results)

    def test_filter_matching_nothing_raises_no_retrieval_results_error(self, retrieval_service, seeded_vector_store):
        with pytest.raises(NoRetrievalResultsError):
            retrieval_service.retrieve("pump seal replacement schedule", department="NonexistentDept")

    def test_top_k_rerank_override_limits_result_count(self, retrieval_service, seeded_vector_store):
        results = retrieval_service.retrieve("pump seal replacement schedule", top_k_rerank=1)
        assert len(results) == 1

    def test_no_retrieval_results_error_carries_query_in_details(self, retrieval_service, seeded_vector_store):
        with pytest.raises(NoRetrievalResultsError) as exc_info:
            retrieval_service.retrieve("anything", department="NonexistentDept")
        assert exc_info.value.details["query"] == "anything"


class TestHealthCheck:
    def test_health_check_aggregates_all_sub_services(self, retrieval_service):
        result = retrieval_service.health_check()
        assert result["healthy"] is True
        assert "embedding_service" in result["details"]
        assert "vector_store_service" in result["details"]
        assert "reranker_service" in result["details"]
