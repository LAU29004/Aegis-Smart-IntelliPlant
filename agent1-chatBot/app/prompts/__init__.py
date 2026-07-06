"""
app/prompts package.

WHY a dedicated `prompts` package: groups the two services that turn
retrieval output into an LLM-ready prompt - `ContextBuilderService`
(numbered source formatting) and `PromptBuilderService` (system
instructions + message assembly). `services/` and `api/` (upcoming
folders) depend on both together as the "prepare this query for the
LLM" step, called after `RetrievalService.retrieve(...)` and before
`llm/`'s Groq client is invoked.
"""

from app.prompts.context_builder_service import ContextBuilderService
from app.prompts.prompt_builder_service import PromptBuilderService, SYSTEM_PROMPT_TEMPLATE
from app.prompts.schemas import ContextBlock, ConversationTurn, SourceReference

__all__ = [
    "ContextBuilderService",
    "PromptBuilderService",
    "SYSTEM_PROMPT_TEMPLATE",
    "ContextBlock",
    "ConversationTurn",
    "SourceReference",
]
