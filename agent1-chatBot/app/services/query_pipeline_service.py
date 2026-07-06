"""
app/services/query_pipeline_service.py

WHY THIS FILE EXISTS
---------------------
This is THE implementation of the spec's full query pipeline:

    User Query -> Embedding -> Vector Search -> Metadata Filtering ->
    Cross Encoder ReRanking -> Context Builder -> Groq LLM ->
    Citation Builder -> Confidence Score -> Follow-up Question
    Generator -> JSON Response

Every stage above is already implemented by its own dedicated,
independently-reusable service (`RetrievalService` covers Embedding
through ReRanking, `ContextBuilderService`, `PromptBuilderService`,
`GroqLLMService`, `CitationBuilderService`, `ConfidenceEngine`,
`FollowUpQuestionService`). This service's ONLY job is SEQUENCING
them correctly, handling the two documented short-circuit/degradation
paths (`NoRetrievalResultsError` and `FollowUpGenerationError`), and
persisting the `QueryLog` + conversation turns for the request.

WHY THIS IS THE ONE PLACE PIPELINE SEQUENCING LIVES
--------------------------------------------------------
Per the spec's Most Important Requirement, every individual capability
must remain independently reusable - which is exactly why none of
them call each other directly. `RetrievalService` doesn't know
`ContextBuilderService` exists; `ContextBuilderService` doesn't know
about Groq. This service is the composition root that wires them
together for the "answer a RAG question" use case specifically. A
future orchestrator combining this agent with Agent 2/3/4 would import
the INDIVIDUAL services directly for its own different compositions,
while `api/`'s `POST /query` route (upcoming folder) calls THIS
service for the standard end-to-end behavior.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import NO_CONTEXT_FOUND_MESSAGE, ConfidenceBand, PipelineStage
from app.core.dependencies import Stopwatch
from app.core.exceptions import FollowUpGenerationError, IntelliPlantBaseException, NoRetrievalResultsError
from app.citations.citation_builder_service import CitationBuilderService
from app.confidence.confidence_engine import ConfidenceEngine
from app.confidence.schemas import ConfidenceResult
from app.database.enums import ConversationRole
from app.database.models import QueryLog
from app.llm.groq_llm_service import GroqLLMService
from app.prompts.context_builder_service import ContextBuilderService
from app.prompts.prompt_builder_service import PromptBuilderService
from app.retrieval.retrieval_service import RetrievalService
from app.services.conversation_memory_service import ConversationMemoryService
from app.services.schemas import QueryPipelineResult
from app.suggestions.followup_service import FollowUpQuestionService


class QueryPipelineService(BaseService):
    """
    Orchestrates the full query pipeline end to end: retrieval,
    context building, LLM generation, citation building, confidence
    scoring, follow-up generation, and persistence.
    """

    def __init__(
        self,
        settings: Settings,
        retrieval_service: RetrievalService,
        context_builder_service: ContextBuilderService,
        prompt_builder_service: PromptBuilderService,
        llm_service: GroqLLMService,
        citation_builder_service: CitationBuilderService,
        confidence_engine: ConfidenceEngine,
        followup_service: FollowUpQuestionService,
        conversation_memory_service: ConversationMemoryService,
    ) -> None:
        super().__init__(settings)
        self.retrieval_service = retrieval_service
        self.context_builder_service = context_builder_service
        self.prompt_builder_service = prompt_builder_service
        self.llm_service = llm_service
        self.citation_builder_service = citation_builder_service
        self.confidence_engine = confidence_engine
        self.followup_service = followup_service
        self.conversation_memory_service = conversation_memory_service

    def answer_query(
        self,
        db: Session,
        query: str,
        *,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        department: Optional[str] = None,
        equipment_id: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> QueryPipelineResult:
        """
        Run one query through the complete pipeline.

        Args:
            db: Request-scoped SQLAlchemy session (see
                `app.database.session.get_db_session`) - used to
                replay/persist conversation history and persist the
                `QueryLog` row. This method does NOT commit; the
                caller's session dependency owns that boundary.
            query: The user's question.
            request_id: Correlation id for logging and the persisted
                `QueryLog` row.
            session_id: Optional conversation grouping id - when
                provided, prior turns are replayed into the LLM prompt
                and both this turn's question and answer are appended
                to history.
            user_id: Optional authenticated user, attached to the
                `QueryLog` row and conversation turns.
            department, equipment_id, document_type: Optional metadata
                filters passed through to `RetrievalService.retrieve`.

        Returns:
            A `QueryPipelineResult` covering every field the spec's
            JSON response requires.

        Raises:
            Any `IntelliPlantBaseException` subclass NOT specifically
            degraded by this method (i.e. everything except
            `NoRetrievalResultsError`, which becomes the spec's exact
            fallback answer, and `FollowUpGenerationError`, which
            degrades to an empty `followups` list) - most notably any
            `GroqAPIError` variant, which represents a genuine failure
            of the main answer generation and must propagate to
            `api/`'s exception handlers rather than being masked here.
        """
        with Stopwatch() as total_timer:
            history = self.conversation_memory_service.get_recent_history(db, session_id) if session_id else []

            try:
                reranked = self.retrieval_service.retrieve(
                    query,
                    department=department,
                    equipment_id=equipment_id,
                    document_type=document_type,
                )
            except NoRetrievalResultsError:
                # WHY this is NOT treated as a pipeline failure: per
                # the spec, an empty result set has an EXACT, defined
                # answer - it is a successful, valid outcome of the
                # pipeline, not an error condition. `was_successful=True`
                # on the persisted QueryLog reflects that.
                return self._handle_no_results(
                    db, query, request_id=request_id, session_id=session_id, user_id=user_id,
                    elapsed_seconds=total_timer.elapsed_seconds,
                )

            try:
                context_block = self.context_builder_service.build(reranked)
                messages = self.prompt_builder_service.build_messages(
                    query, context_block, conversation_history=history
                )
                llm_response = self.llm_service.generate_completion(messages)

                citations = self.citation_builder_service.build_citations(
                    llm_response.content, context_block.sources
                )
                related_documents = self.citation_builder_service.build_related_documents(
                    context_block.sources
                )
                confidence_result = self.confidence_engine.compute(reranked)

                followups = self._generate_followups_gracefully(
                    query, llm_response.content, related_documents
                )

                self._persist_success(
                    db,
                    query=query,
                    answer=llm_response.content,
                    request_id=request_id,
                    session_id=session_id,
                    user_id=user_id,
                    context_block=context_block,
                    confidence_result=confidence_result,
                    elapsed_seconds=total_timer.elapsed_seconds,
                )
            except IntelliPlantBaseException as exc:
                self._persist_failure(db, query, request_id, session_id, user_id, exc)
                raise

        return QueryPipelineResult(
            answer=llm_response.content,
            citations=citations,
            confidence=confidence_result,
            followups=followups,
            related_documents=related_documents,
            processing_time_seconds=total_timer.elapsed_seconds,
            request_id=request_id,
        )

    def _generate_followups_gracefully(self, query, answer, related_documents):
        """
        WHY this tiny wrapper exists as its own method rather than an
        inline try/except in `answer_query`: isolates the ONE
        documented graceful-degradation path in this pipeline (follow-
        ups are best-effort) so it can't accidentally be conflated
        with the outer `except IntelliPlantBaseException` block, which
        must NOT catch `FollowUpGenerationError` - if it did, a failed
        follow-up generation would incorrectly mark the ENTIRE query
        as failed and roll back an otherwise-successful answer.
        """
        try:
            return self.followup_service.generate(
                query, answer, source_document_names=[d.document_name for d in related_documents]
            )
        except FollowUpGenerationError as exc:
            self.logger.bind(stage=PipelineStage.FOLLOWUP_GENERATION.value).warning(
                f"Follow-up generation failed, degrading to empty list: {exc.message}"
            )
            return []

    def _handle_no_results(self, db, query, *, request_id, session_id, user_id, elapsed_seconds):
        """Builds and persists the spec's exact no-context-found response."""
        confidence_result = ConfidenceResult(
            score=0.0, band=ConfidenceBand.RED, primary_relevance_score=0.0,
            contributing_chunk_count=0, per_source_scores=[],
        )
        query_log = QueryLog(
            request_id=request_id or str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            query_text=query,
            answer_text=NO_CONTEXT_FOUND_MESSAGE,
            confidence_score=0.0,
            confidence_band=ConfidenceBand.RED,
            retrieved_chunk_ids=[],
            processing_time_ms=elapsed_seconds * 1000,
            was_successful=True,
        )
        db.add(query_log)
        if session_id:
            self.conversation_memory_service.append_turn(
                db, session_id, ConversationRole.USER, query, user_id=user_id
            )
            self.conversation_memory_service.append_turn(
                db, session_id, ConversationRole.ASSISTANT, NO_CONTEXT_FOUND_MESSAGE, user_id=user_id
            )
        return QueryPipelineResult(
            answer=NO_CONTEXT_FOUND_MESSAGE,
            citations=[],
            confidence=confidence_result,
            followups=[],
            related_documents=[],
            processing_time_seconds=elapsed_seconds,
            request_id=request_id,
        )

    def _persist_success(
        self, db, *, query, answer, request_id, session_id, user_id,
        context_block, confidence_result, elapsed_seconds,
    ):
        query_log = QueryLog(
            request_id=request_id or str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            query_text=query,
            answer_text=answer,
            confidence_score=confidence_result.score,
            confidence_band=confidence_result.band,
            retrieved_chunk_ids=[s.chunk_id for s in context_block.sources],
            processing_time_ms=elapsed_seconds * 1000,
            was_successful=True,
        )
        db.add(query_log)
        if session_id:
            self.conversation_memory_service.append_turn(
                db, session_id, ConversationRole.USER, query, user_id=user_id
            )
            self.conversation_memory_service.append_turn(
                db, session_id, ConversationRole.ASSISTANT, answer, user_id=user_id
            )

    def _persist_failure(self, db, query, request_id, session_id, user_id, exc: IntelliPlantBaseException):
        """
        WHY failures are BEST-EFFORT logged (wrapped in their own
        try/except that swallows secondary errors): if persisting the
        failure log itself fails (e.g. the database is what's down),
        we must not let THAT secondary exception mask and replace the
        original, more informative error the caller needs to see and
        the `exception_handlers.py` layer needs to report correctly.
        """
        try:
            db.add(
                QueryLog(
                    request_id=request_id or str(uuid.uuid4()),
                    session_id=session_id,
                    user_id=user_id,
                    query_text=query,
                    answer_text=None,
                    was_successful=False,
                    error_code=exc.error_code.value,
                )
            )
            db.flush()
        except Exception:
            self.logger.bind(stage=PipelineStage.RESPONSE_ASSEMBLY.value).warning(
                "Failed to persist failed-query log entry - continuing to "
                "propagate the original error."
            )

    def health_check(self) -> dict:
        """
        Aggregates health across every sub-service this orchestrator
        depends on.
        """
        sub_checks = {
            "retrieval_service": self.retrieval_service.health_check(),
            "llm_service": self.llm_service.health_check(),
            "followup_service": self.followup_service.health_check(),
            "conversation_memory_service": self.conversation_memory_service.health_check(),
        }
        all_healthy = all(check["healthy"] for check in sub_checks.values())
        return {
            "service": self.service_name,
            "healthy": all_healthy,
            "details": sub_checks,
        }
