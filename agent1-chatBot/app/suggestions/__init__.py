"""
app/suggestions package.

WHY a dedicated `suggestions` package: implements the "Follow-up
Question Generator" pipeline stage as its own service
(`FollowUpQuestionService`), kept separate from `prompts/` even though
both build LLM prompts - `prompts/` builds the hallucination-resistant
QA prompt with the strict "only answer from context" system prompt,
while this stage builds a DIFFERENT, deliberately more permissive
prompt for a fundamentally different (and non-critical) purpose.
Conflating the two into one module would risk the follow-up prompt's
looser instructions accidentally bleeding into the QA prompt's much
stricter hallucination-resistance requirements.
"""

from app.suggestions.followup_service import FollowUpQuestionService

__all__ = [
    "FollowUpQuestionService",
]
