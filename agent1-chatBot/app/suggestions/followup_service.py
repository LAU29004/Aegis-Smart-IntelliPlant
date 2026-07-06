"""
app/suggestions/followup_service.py

WHY THIS FILE EXISTS
---------------------
Implements the "Follow-up Question Generator" pipeline stage: given
the user's question and the answer just produced, asks Groq (via the
SAME `GroqLLMService` the main QA pipeline uses - see module
docstring of `app/llm/groq_llm_service.py` for why that service is
deliberately generic) for exactly `Settings.FOLLOWUP_QUESTION_COUNT`
natural follow-up questions, and parses its JSON-array response.

WHY THIS STAGE IS DELIBERATELY BEST-EFFORT
----------------------------------------------
`FollowUpGenerationError` (see `core/exceptions.py`) exists
specifically so this stage's failure mode is DIFFERENT from every
other Groq-dependent stage: the caller (the upcoming `services/`
query orchestrator) is expected to catch `FollowUpGenerationError`
specifically and return `followups: []` while still returning the
main answer intact, rather than failing the entire request. A
follow-up suggestion is a nice-to-have UX enhancement, not a claim
the user might act on the way a maintenance answer is - it does not
deserve the same all-or-nothing failure treatment as
`GroqAPIError` during the main answer generation.
"""

import json
import re
from typing import List, Optional

from app.config.settings import Settings
from app.core.base_service import BaseService
from app.core.constants import PipelineStage
from app.core.exceptions import FollowUpGenerationError, GroqAPIError
from app.llm.groq_llm_service import GroqLLMService

# WHY the model is explicitly instructed to return ONLY a JSON array,
# with no markdown fences or preamble: structured output is far more
# reliably parseable than asking for "three questions, one per line"
# and hoping the model's formatting is consistent. Even so, `_parse_questions`
# below defensively strips markdown code fences, since models
# sometimes wrap JSON in ```json ... ``` despite instructions not to.
_SYSTEM_PROMPT_TEMPLATE = """You generate follow-up questions for an industrial plant knowledge \
assistant. Given a question a plant engineer or technician asked and the answer they were given, \
suggest natural, relevant follow-up questions they might ask next - the kind of questions someone \
actually doing maintenance, safety, or compliance work would think to ask after reading that \
answer.

Respond with ONLY a JSON array of exactly {count} short question strings. Do not include \
markdown code fences, explanations, numbering, or any text outside the JSON array itself. \
Example valid response: ["Question one?", "Question two?", "Question three?"]"""

# WHY this pattern: strips a leading/trailing ```json or ``` fence if
# present, so `json.loads` receives clean JSON even when the model
# ignored the "no markdown fences" instruction.
_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class FollowUpQuestionService(BaseService):
    """
    Generates natural follow-up questions for a completed query/answer
    pair, using Groq with a dedicated (non-QA) prompt.
    """

    def __init__(self, settings: Settings, llm_service: GroqLLMService) -> None:
        """
        Args:
            settings: Validated application settings - specifically
                `FOLLOWUP_QUESTION_COUNT`.
            llm_service: The SAME shared `GroqLLMService` instance the
                main QA pipeline uses - injected rather than
                constructed here so both stages share one Groq client
                and one retry/error-handling policy.
        """
        super().__init__(settings)
        self.llm_service = llm_service

    def generate(
        self,
        query: str,
        answer: str,
        source_document_names: Optional[List[str]] = None,
        count: Optional[int] = None,
    ) -> List[str]:
        """
        Generate follow-up questions for a completed query/answer.

        Args:
            query: The user's original question.
            answer: The answer that was generated for it.
            source_document_names: Optional distinct document names
                the answer drew from (e.g. from
                `RelatedDocument.document_name`) - included as light
                context to keep suggested follow-ups grounded in the
                same subject area, without needing the FULL context
                block (which would make this call unnecessarily
                expensive for a nice-to-have feature).
            count: Override for `Settings.FOLLOWUP_QUESTION_COUNT`.

        Returns:
            Up to `count` follow-up question strings. May return
            FEWER than `count` if the model legitimately produced
            fewer (this is NOT treated as an error - a shorter but
            valid list is still useful). Returns an empty list
            immediately, without calling Groq at all, if the
            effective count is 0 (i.e. this feature is disabled via
            settings).

        Raises:
            FollowUpGenerationError: if `query`/`answer` are empty, if
                the Groq call itself fails, or if the response cannot
                be parsed as a JSON array of strings. Per the module
                docstring, callers should catch this specifically and
                degrade to an empty list rather than failing the
                whole request.
        """
        effective_count = (
            count if count is not None else self.settings.FOLLOWUP_QUESTION_COUNT
        )
        if effective_count <= 0:
            return []

        if not query or not query.strip() or not answer or not answer.strip():
            raise FollowUpGenerationError(
                "Cannot generate follow-up questions from an empty query "
                "or answer.",
                stage=PipelineStage.FOLLOWUP_GENERATION,
            )

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(count=effective_count)
        user_content_parts = [
            f"Original question: {query.strip()}",
            f"Answer given: {answer.strip()}",
        ]
        if source_document_names:
            # WHY deduplicated with `dict.fromkeys` rather than
            # `set(...)`: preserves the original order the caller
            # provided (typically relevance order from
            # `RelatedDocument`), whereas a set would scramble it.
            unique_names = list(dict.fromkeys(source_document_names))
            user_content_parts.append(f"Related documents: {', '.join(unique_names)}")
        user_content_parts.append(
            f"Generate exactly {effective_count} follow-up question(s)."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n\n".join(user_content_parts)},
        ]

        try:
            # WHY temperature=0.4 (higher than the main QA pipeline's
            # GROQ_TEMPERATURE, typically 0.1): follow-up questions
            # benefit from a bit more variety/naturalness than a
            # strictly factual answer does - this call is not at risk
            # of "hallucinating" in the harmful sense, since a
            # follow-up question is a suggestion, not a factual claim.
            # WHY max_tokens=300: a JSON array of a handful of short
            # questions needs far fewer tokens than a full answer;
            # capping it low keeps this best-effort stage cheap.
            response = self.llm_service.generate_completion(
                messages, temperature=0.4, max_tokens=300
            )
        except GroqAPIError as exc:
            # WHY GroqAPIError specifically (which also catches its
            # subclasses GroqTimeoutError/GroqRateLimitError/
            # GroqAuthenticationError, per core/exceptions.py's
            # hierarchy): ANY Groq-side failure during this best-effort
            # stage becomes a FollowUpGenerationError, so callers only
            # ever need to catch ONE exception type to implement the
            # "degrade to empty list" behavior this stage promises.
            raise FollowUpGenerationError(
                "Follow-up question generation failed due to an LLM error.",
                stage=PipelineStage.FOLLOWUP_GENERATION,
                original_exception=exc,
            ) from exc

        return self._parse_questions(response.content, effective_count)

    def _parse_questions(self, raw_content: str, expected_count: int) -> List[str]:
        """
        Parse the model's response as a JSON array of question
        strings, defensively stripping markdown code fences first.

        WHY malformed JSON raises rather than falling back to some
        naive line-splitting heuristic: a heuristic fallback would
        silently produce lower-quality results (e.g. splitting on
        newlines could turn one multi-line question into two garbled
        fragments) without any signal that something went wrong.
        Raising `FollowUpGenerationError` lets the caller's documented
        "degrade to empty list" behavior handle it cleanly and
        visibly (via logs), rather than silently shipping malformed
        suggestions to the user.
        """
        cleaned = _CODE_FENCE_PATTERN.sub("", raw_content).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise FollowUpGenerationError(
                "Groq did not return valid JSON for follow-up questions.",
                stage=PipelineStage.FOLLOWUP_GENERATION,
                details={"raw_content_preview": raw_content[:200]},
                original_exception=exc,
            ) from exc

        if not isinstance(parsed, list) or not all(isinstance(q, str) for q in parsed):
            raise FollowUpGenerationError(
                "Groq returned JSON that was not a list of question strings.",
                stage=PipelineStage.FOLLOWUP_GENERATION,
                details={"raw_content_preview": raw_content[:200]},
            )

        questions = [q.strip() for q in parsed if q.strip()]
        return questions[:expected_count]

    def health_check(self) -> dict:
        """
        Verifies end-to-end follow-up generation against a small
        probe query/answer pair, including a real Groq round-trip via
        `self.llm_service`.
        """
        try:
            questions = self.generate(
                query="What is the health check probe procedure?",
                answer="This is a health check probe answer used only for diagnostics.",
                count=2,
            )
            healthy = isinstance(questions, list)
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {"probe_question_count": len(questions)},
            }
        except FollowUpGenerationError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
