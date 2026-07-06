"""
app/llm package.

WHY a dedicated `llm` package: isolates the ONE dependency on the
Groq SDK behind `GroqLLMService`, matching the same pattern every
other external-model dependency in this codebase follows
(`embeddings/` for Sentence-Transformers, `retrieval/` for ChromaDB).
`services/` (upcoming folder, the main query orchestrator) and
`suggestions/` (follow-up question generation) both depend on THIS
service for any LLM call - neither imports `groq` directly.
"""

from app.llm.groq_llm_service import GroqLLMService
from app.llm.schemas import LLMResponse

__all__ = [
    "GroqLLMService",
    "LLMResponse",
]
