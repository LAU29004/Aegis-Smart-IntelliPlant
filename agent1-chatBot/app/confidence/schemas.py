"""
app/confidence/schemas.py

WHY THIS FILE EXISTS
---------------------
`ConfidenceResult` is the single output shape of the "Confidence
Score" pipeline stage - carries not just the final 0-100 score and
Green/Amber/Red band the spec requires in the API response, but also
the intermediate signals (`primary_relevance_score`,
`per_source_scores`) that make the final number explainable in logs
and, potentially, in a future debugging UI. Without these, a
confidence score of e.g. 42 is just an opaque number; with them, it's
traceable to exactly which chunk drove it and how strongly.
"""

from dataclasses import dataclass, field
from typing import List

from app.core.constants import ConfidenceBand


@dataclass(frozen=True)
class ConfidenceResult:
    """
    The result of scoring a set of reranked chunks for how confidently
    they support an answer.

    Attributes:
        score: Final 0-100 confidence score, per the spec.
        band: `ConfidenceBand.GREEN` / `.AMBER` / `.RED`, derived from
            `score` against `Settings.CONFIDENCE_GREEN_THRESHOLD` /
            `Settings.CONFIDENCE_AMBER_THRESHOLD`.
        primary_relevance_score: The raw cross-encoder score of the
            SINGLE highest-ranked chunk, before any normalization or
            blending - the single biggest driver of `score`, retained
            for observability (e.g. logging/alerting on unusually low
            top-match scores even when the blended `score` still
            lands in a passable band).
        contributing_chunk_count: How many reranked chunks factored
            into this computation.
        per_source_scores: One normalized (0-100) score per reranked
            chunk, in the same order as the input - lets a caller see
            the full relevance distribution, not just the single
            blended number.
    """

    score: float
    band: ConfidenceBand
    primary_relevance_score: float
    contributing_chunk_count: int
    per_source_scores: List[float] = field(default_factory=list)
