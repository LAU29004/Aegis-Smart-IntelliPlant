"""
app/confidence package.

WHY a dedicated `confidence` package: implements the "Confidence
Score" pipeline stage as its own service, consumed by `services/`
(upcoming folder) directly on the reranked results - it does NOT
depend on the LLM having generated an answer yet (unlike
`citations/`, which parses the LLM's output). This means confidence
can, in principle, be computed in parallel with the Groq call rather
than strictly after it, since both stages only need
`RetrievalService.retrieve(...)`'s output.
"""

from app.confidence.confidence_engine import ConfidenceEngine
from app.confidence.schemas import ConfidenceResult

__all__ = [
    "ConfidenceEngine",
    "ConfidenceResult",
]
