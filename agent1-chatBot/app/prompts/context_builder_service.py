"""
app/prompts/context_builder_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Context Builder" pipeline stage: takes the reranked
chunks from `RetrievalService.retrieve(...)` and formats them into a
single, numbered block of text the LLM will be instructed to answer
ONLY from. This is also where the citation numbering scheme (`[1]`,
`[2]`, ...) that both the LLM's answer AND the eventual
`CitationBuilderService` (upcoming `citations/` folder) rely on is
first assigned - see `app/prompts/schemas.py::SourceReference` for
why that numbering must be authoritative and consistent.

WHY this stage also enforces a context size budget: `RetrievalService`
already caps candidates at `TOP_K_AFTER_RERANK` (5 by default), which
keeps context size naturally bounded in the common case. But chunk
content length itself is only approximately bounded by
`CHUNK_SIZE_TOKENS` (the offline word-tokenizer's "tokens" are words,
not the LLM's actual subword tokens, and can run longer in
characters for verbose technical text) - a defensive word-count
budget here is what actually protects `GROQ_MAX_TOKENS`/the model's
context window from ever being exceeded by the assembled prompt,
regardless of chunk content variance.
"""

from typing import List

from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import PromptBuildError
from app.embeddings.schemas import RerankResult
from app.prompts.schemas import ContextBlock, SourceReference

# WHY this specific budget: TOP_K_AFTER_RERANK (5) chunks at
# CHUNK_SIZE_TOKENS (512 words each) is ~2560 words in the ordinary
# case. This budget is set generously above that (6000 words) so it
# only ever engages as a genuine safety net - e.g. against unusually
# verbose chunk content, or a caller passing a larger top_k override -
# rather than routinely truncating normal-sized result sets.
DEFAULT_MAX_CONTEXT_WORDS = 6000


class ContextBuilderService(BaseService):
    """
    Formats reranked retrieval results into a single, numbered context
    block ready to be embedded in the LLM prompt.
    """

    def build(
        self,
        reranked_results: List[RerankResult],
        *,
        max_context_words: int = DEFAULT_MAX_CONTEXT_WORDS,
    ) -> ContextBlock:
        """
        Args:
            reranked_results: Output of `RetrievalService.retrieve(...)`,
                already sorted by relevance descending. MUST be
                non-empty - `RetrievalService` is responsible for
                raising `NoRetrievalResultsError` before this stage is
                ever reached with zero results; this method treats an
                empty list as a programming error, not an expected case
                to degrade gracefully from.
            max_context_words: Defensive word-count budget (see module
                docstring). Chunks are included in relevance order
                (highest first) until the budget would be exceeded;
                any remaining lower-relevance chunks are dropped.

        Returns:
            A `ContextBlock` with formatted `context_text` and the
            authoritative, index-aligned `sources` list.

        Raises:
            PromptBuildError: if `reranked_results` is empty, or if
                every single result would individually exceed
                `max_context_words` on its own (meaning NOTHING could
                be included, which would produce an empty, useless
                context block).
        """
        if not reranked_results:
            raise PromptBuildError(
                "Cannot build context from an empty result set - this "
                "indicates a caller invoked ContextBuilderService without "
                "first checking for NoRetrievalResultsError upstream.",
                stage=PipelineStage.CONTEXT_BUILDING,
            )

        sources: List[SourceReference] = []
        formatted_sections: List[str] = []
        running_word_count = 0
        truncated = False

        for position, result in enumerate(reranked_results, start=1):
            content_word_count = len(result.text.split())
            if running_word_count + content_word_count > max_context_words:
                if not formatted_sections:
                    # WHY this specific case (the very FIRST, highest-
                    # relevance chunk alone already exceeds budget) is a
                    # hard error rather than silently truncating that
                    # single chunk's text: truncating mid-chunk risks
                    # cutting off a procedure or safety instruction
                    # mid-sentence, which is far more dangerous in an
                    # industrial context than failing loudly and letting
                    # the caller decide how to handle an oversized chunk
                    # (e.g. by lowering CHUNK_SIZE_TOKENS).
                    raise PromptBuildError(
                        "The single highest-relevance chunk alone exceeds "
                        "the context word budget - reduce CHUNK_SIZE_TOKENS "
                        "or increase max_context_words.",
                        stage=PipelineStage.CONTEXT_BUILDING,
                        details={
                            "chunk_word_count": content_word_count,
                            "max_context_words": max_context_words,
                        },
                    )
                truncated = True
                break

            page_number = result.metadata.get("page_number")
            source = SourceReference(
                index=position,
                chunk_id=result.chunk_id,
                document_name=result.metadata.get("document_name", "Unknown document"),
                page_number=page_number,
                department=result.metadata.get("department"),
                equipment_id=result.metadata.get("equipment_id"),
                relevance_score=result.score,
            )
            sources.append(source)

            page_label = f", Page {page_number}" if page_number else ""
            formatted_sections.append(
                f"[{position}] Source: {source.document_name}{page_label}\n{result.text}"
            )
            running_word_count += content_word_count

        context_text = "\n\n".join(formatted_sections)

        self.logger.bind(stage=PipelineStage.CONTEXT_BUILDING.value).debug(
            f"Built context from {len(sources)}/{len(reranked_results)} "
            f"chunk(s), {running_word_count} word(s), truncated={truncated}"
        )
        return ContextBlock(context_text=context_text, sources=sources, truncated=truncated)

    def health_check(self) -> dict:
        """
        Verifies context building produces correctly numbered,
        correctly formatted output on a small probe result set.
        """
        try:
            probe_results = [
                RerankResult(
                    chunk_id="probe-1",
                    text="Replace the seal every six months.",
                    score=4.0,
                    metadata={"document_name": "Probe Manual.pdf", "page_number": 1},
                )
            ]
            block = self.build(probe_results)
            healthy = (
                len(block.sources) == 1
                and block.sources[0].index == 1
                and "[1]" in block.context_text
                and "Probe Manual.pdf" in block.context_text
            )
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {"default_max_context_words": DEFAULT_MAX_CONTEXT_WORDS},
            }
        except PromptBuildError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
