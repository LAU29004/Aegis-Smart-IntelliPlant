"""
app/api/dependencies.py

WHY THIS FILE EXISTS
---------------------
This is the ONE place, in the entire codebase, where every service
from every folder gets CONSTRUCTED and wired together -
`EmbeddingService`, `VectorStoreService`, `RetrievalService`,
`GroqLLMService`, `ContextBuilderService`, `PromptBuilderService`,
`CitationBuilderService`, `ConfidenceEngine`, `FollowUpQuestionService`,
`ConversationMemoryService`, `QueryPipelineService`,
`DocumentIngestionService`'s four sub-services, and
`DocumentUploadPipelineService`. Every other file in this codebase
that needs one of these services receives it via constructor
injection (see each service's `__init__`) - THIS file is where those
constructors actually get called, exactly once per process, at
application startup.

WHY THIS LIVES IN `api/` AND NOT `services/`
-------------------------------------------------
`services/` contains the individually-reusable ORCHESTRATION services
themselves (`QueryPipelineService`, etc.) - they know nothing about
HOW they get constructed or by whom. THIS file is FastAPI-specific
wiring: it builds the `ServiceRegistry`, stores it on `app.state`
during the lifespan startup (see `app/main.py`), and exposes
`Depends(...)`-compatible provider functions that route handlers use
to receive services from that registry. A future Agent Orchestrator
importing `QueryPipelineService` directly would construct its OWN
wiring, entirely bypassing this file - which is exactly the point:
this file is Agent 1's OWN FastAPI app's composition root, not a
reusable library component.
"""

from dataclasses import dataclass

from fastapi import Depends, Request

from app.citations.citation_builder_service import CitationBuilderService
from app.confidence.confidence_engine import ConfidenceEngine
from app.config.settings import Settings
from app.embeddings.embedding_service import EmbeddingService
from app.embeddings.reranker_service import CrossEncoderRerankerService
from app.ingestion.chunking_service import ChunkingService
from app.ingestion.cleaning_service import TextCleaningService
from app.ingestion.document_ingestion_service import DocumentIngestionService
from app.ingestion.ocr_service import OCRService
from app.ingestion.text_extraction_service import TextExtractionService
from app.llm.groq_llm_service import GroqLLMService
from app.prompts.context_builder_service import ContextBuilderService
from app.prompts.prompt_builder_service import PromptBuilderService
from app.retrieval.retrieval_service import RetrievalService
from app.retrieval.vector_store_service import VectorStoreService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.document_upload_pipeline_service import DocumentUploadPipelineService
from app.services.query_pipeline_service import QueryPipelineService
from app.suggestions.followup_service import FollowUpQuestionService


@dataclass
class ServiceRegistry:
    """
    Holds every constructed service singleton for the process's
    lifetime. One instance of this is created in `app/main.py`'s
    lifespan startup and stored on `app.state.service_registry`.

    WHY a plain dataclass rather than, say, a dependency-injection
    framework (e.g. `dependency-injector`): the service graph here is
    small and static (it never changes shape at runtime) - a plain
    dataclass built by one explicit function (`build_service_registry`
    below) is easier to read top-to-bottom, easier to debug (no
    framework magic between "I asked for X" and "here is X"), and adds
    zero additional dependencies for a problem this codebase's size
    doesn't need a framework to solve.
    """

    settings: Settings
    embedding_service: EmbeddingService
    reranker_service: CrossEncoderRerankerService
    vector_store_service: VectorStoreService
    retrieval_service: RetrievalService
    llm_service: GroqLLMService
    query_pipeline_service: QueryPipelineService
    upload_pipeline_service: DocumentUploadPipelineService
    conversation_memory_service: ConversationMemoryService

    def warm_up_local_services(self) -> None:
        """
        Force the LOCAL (non-Groq) model-backed services to load their
        models now, during application startup, rather than lazily on
        whichever request happens to be first.

        WHY GROQ IS DELIBERATELY EXCLUDED FROM STARTUP WARM-UP
        ------------------------------------------------------------
        `GroqLLMService` is NOT warmed up here. Warming it would mean
        every single application restart (routine deploys, container
        rescheduling, local development reloads) makes a real,
        billed API call to Groq before the app can even start serving
        traffic - for local services (embedding, reranker, ChromaDB)
        "warming up" means loading a model already present on disk,
        which costs time but not money and has no external dependency
        that could fail unrelated to THIS deployment. Groq's health is
        instead checked lazily (on first real use) and via `GET /health`
        when explicitly requested with `deep=true` - see
        `app/api/routes/health_routes.py`.
        """
        self.embedding_service.warm_up()
        self.reranker_service.warm_up()
        self.vector_store_service.warm_up()


def build_service_registry(settings: Settings) -> ServiceRegistry:
    """
    Construct the entire service dependency graph, exactly once.

    WHY the construction order below matters: every service that
    depends on another (e.g. `RetrievalService` depends on
    `EmbeddingService`, `VectorStoreService`, and
    `CrossEncoderRerankerService`) requires its dependencies to
    already exist as objects to be passed into its constructor - this
    function is written in dependency order (leaves first, composites
    last) for exactly that reason. Reordering it incorrectly would
    simply fail with a `NameError` at startup, which is a deliberate,
    fail-fast property of doing this wiring explicitly rather than
    through a framework that resolves ordering automatically (and
    therefore could silently paper over a circular dependency that
    SHOULD be a startup error).
    """
    # --- Embedding / retrieval building blocks ---
    embedding_service = EmbeddingService(settings)
    reranker_service = CrossEncoderRerankerService(settings)
    vector_store_service = VectorStoreService(settings)
    retrieval_service = RetrievalService(
        settings, embedding_service, vector_store_service, reranker_service
    )

    # --- Prompt / LLM / citation / confidence / follow-up building blocks ---
    context_builder_service = ContextBuilderService(settings)
    prompt_builder_service = PromptBuilderService(settings)
    llm_service = GroqLLMService(settings)
    citation_builder_service = CitationBuilderService(settings)
    confidence_engine = ConfidenceEngine(settings)
    followup_service = FollowUpQuestionService(settings, llm_service)
    conversation_memory_service = ConversationMemoryService(settings)

    query_pipeline_service = QueryPipelineService(
        settings,
        retrieval_service,
        context_builder_service,
        prompt_builder_service,
        llm_service,
        citation_builder_service,
        confidence_engine,
        followup_service,
        conversation_memory_service,
    )

    # --- Ingestion building blocks ---
    text_extraction_service = TextExtractionService(settings)
    ocr_service = OCRService(settings)
    cleaning_service = TextCleaningService(settings)
    chunking_service = ChunkingService(settings)
    document_ingestion_service = DocumentIngestionService(
        settings, text_extraction_service, ocr_service, cleaning_service, chunking_service
    )
    upload_pipeline_service = DocumentUploadPipelineService(
        settings, document_ingestion_service, embedding_service, vector_store_service
    )

    return ServiceRegistry(
        settings=settings,
        embedding_service=embedding_service,
        reranker_service=reranker_service,
        vector_store_service=vector_store_service,
        retrieval_service=retrieval_service,
        llm_service=llm_service,
        query_pipeline_service=query_pipeline_service,
        upload_pipeline_service=upload_pipeline_service,
        conversation_memory_service=conversation_memory_service,
    )


def get_service_registry(request: Request) -> ServiceRegistry:
    """
    FastAPI dependency returning the process-wide `ServiceRegistry`.

    WHY read from `request.app.state` rather than a module-level
    global: `app.state` is the FastAPI-idiomatic place for
    startup-constructed, request-lifetime-spanning objects, and (unlike
    a bare module global) it is naturally scoped to a single `FastAPI`
    app instance - important for testability, since a test can spin up
    its own `FastAPI` app with its own registry without any risk of
    cross-contamination with another app instance in the same process
    (e.g. multiple test cases each constructing a fresh app).
    """
    return request.app.state.service_registry


def get_query_pipeline_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> QueryPipelineService:
    return registry.query_pipeline_service


def get_upload_pipeline_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> DocumentUploadPipelineService:
    return registry.upload_pipeline_service


def get_conversation_memory_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ConversationMemoryService:
    return registry.conversation_memory_service
