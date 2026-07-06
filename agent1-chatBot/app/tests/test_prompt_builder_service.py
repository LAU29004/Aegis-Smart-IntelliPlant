"""
app/tests/test_prompt_builder_service.py

Unit tests for `app.prompts.context_builder_service.ContextBuilderService`
and `app.prompts.prompt_builder_service.PromptBuilderService`, per the
spec's explicit "Generate unit tests for ... Prompt Builder"
requirement. Context building is tested alongside prompt building
since the latter's input (`ContextBlock`) is entirely produced by the
former - testing them together mirrors how they're actually used in
the real pipeline.
"""

import pytest

from app.core.constants import NO_CONTEXT_FOUND_MESSAGE
from app.core.exceptions import PromptBuildError
from app.embeddings.schemas import RerankResult
from app.prompts.context_builder_service import ContextBuilderService
from app.prompts.prompt_builder_service import PromptBuilderService
from app.prompts.schemas import ContextBlock, ConversationTurn, SourceReference


@pytest.fixture
def context_builder(settings) -> ContextBuilderService:
    return ContextBuilderService(settings)


@pytest.fixture
def prompt_builder(settings) -> PromptBuilderService:
    return PromptBuilderService(settings)


def _rerank_results():
    return [
        RerankResult(chunk_id="c1", text="Replace the pump seal every 6 months.", score=4.0,
                     metadata={"document_name": "Pump Manual.pdf", "page_number": 3, "department": "Maintenance"}),
        RerankResult(chunk_id="c2", text="Bearing lubrication is performed quarterly.", score=2.5,
                     metadata={"document_name": "Pump Manual.pdf", "page_number": 4}),
        RerankResult(chunk_id="c3", text="Vibration checks confirm normal operation.", score=1.0,
                     metadata={"document_name": "Inspection Log.pdf", "page_number": 12}),
    ]


class TestContextBuilder:
    def test_build_assigns_sequential_citation_numbers(self, context_builder):
        block = context_builder.build(_rerank_results())
        assert [s.index for s in block.sources] == [1, 2, 3]

    def test_build_preserves_source_relevance_order(self, context_builder):
        block = context_builder.build(_rerank_results())
        assert block.sources[0].chunk_id == "c1"
        assert block.sources[0].relevance_score == 4.0

    def test_context_text_contains_numbered_markers(self, context_builder):
        block = context_builder.build(_rerank_results())
        assert "[1]" in block.context_text
        assert "[3]" in block.context_text

    def test_context_text_includes_document_name_and_page(self, context_builder):
        block = context_builder.build(_rerank_results())
        assert "Pump Manual.pdf" in block.context_text
        assert "Page 3" in block.context_text

    def test_empty_result_set_raises_prompt_build_error(self, context_builder):
        with pytest.raises(PromptBuildError):
            context_builder.build([])

    def test_not_truncated_under_normal_conditions(self, context_builder):
        block = context_builder.build(_rerank_results())
        assert block.truncated is False

    def test_truncation_drops_lower_relevance_chunks_when_over_budget(self, context_builder):
        huge_text = " ".join(["word"] * 5000)
        results = [
            RerankResult(chunk_id="big1", text=huge_text, score=5.0, metadata={"document_name": "Big.pdf"}),
            RerankResult(chunk_id="big2", text=huge_text, score=4.0, metadata={"document_name": "Big.pdf"}),
            RerankResult(chunk_id="small", text="short text", score=3.0, metadata={"document_name": "Small.pdf"}),
        ]
        block = context_builder.build(results, max_context_words=6000)
        assert block.truncated is True
        assert len(block.sources) == 1
        assert block.sources[0].chunk_id == "big1"

    def test_single_chunk_exceeding_budget_alone_raises_hard_error(self, context_builder):
        oversized = [
            RerankResult(chunk_id="x", text=" ".join(["word"] * 7000), score=1.0, metadata={"document_name": "X.pdf"})
        ]
        with pytest.raises(PromptBuildError):
            context_builder.build(oversized, max_context_words=6000)


class TestPromptBuilder:
    def test_build_messages_starts_with_system_message(self, context_builder, prompt_builder):
        block = context_builder.build(_rerank_results())
        messages = prompt_builder.build_messages("How often should I replace the seal?", block)
        assert messages[0]["role"] == "system"

    def test_system_message_contains_exact_fallback_string(self, context_builder, prompt_builder):
        block = context_builder.build(_rerank_results())
        messages = prompt_builder.build_messages("query", block)
        assert NO_CONTEXT_FOUND_MESSAGE in messages[0]["content"]

    def test_final_message_is_user_role_and_contains_question(self, context_builder, prompt_builder):
        block = context_builder.build(_rerank_results())
        messages = prompt_builder.build_messages("What about bearing lubrication?", block)
        assert messages[-1]["role"] == "user"
        assert "bearing lubrication" in messages[-1]["content"].lower()

    def test_conversation_history_is_replayed_in_correct_order(self, context_builder, prompt_builder):
        block = context_builder.build(_rerank_results())
        history = [
            ConversationTurn(role="user", content="What is PUMP-101?"),
            ConversationTurn(role="assistant", content="It is the primary feed pump. [1]"),
        ]
        messages = prompt_builder.build_messages("Follow-up question?", block, conversation_history=history)

        assert len(messages) == 4  # system + 2 history turns + final user
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_empty_query_raises_prompt_build_error(self, context_builder, prompt_builder):
        block = context_builder.build(_rerank_results())
        with pytest.raises(PromptBuildError):
            prompt_builder.build_messages("   ", block)

    def test_context_block_with_no_sources_raises_prompt_build_error(self, prompt_builder):
        empty_block = ContextBlock(context_text="", sources=[])
        with pytest.raises(PromptBuildError):
            prompt_builder.build_messages("valid query", empty_block)


class TestHealthChecks:
    def test_context_builder_health_check(self, context_builder):
        assert context_builder.health_check()["healthy"] is True

    def test_prompt_builder_health_check(self, prompt_builder):
        assert prompt_builder.health_check()["healthy"] is True
