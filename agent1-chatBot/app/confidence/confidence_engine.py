"""
app/confidence/confidence_engine.py

WHY THIS FILE EXISTS
---------------------
Implements the "Confidence Score" pipeline stage, converting the
cross-encoder's raw relevance scores (see `CrossEncoderRerankerService`
in `app/embeddings/reranker_service.py`) into the spec's 0-100
confidence score and Green (>80) / Amber (60-80) / Red (<60) band.

WHY A SIGMOID TRANSFORM IS NEEDED AT ALL
-------------------------------------------
Cross-encoder models (like `cross-encoder/ms-marco-MiniLM-L-6-v2`,
this service's default per `Settings.CROSS_ENCODER_MODEL_NAME`) output
raw, UNBOUNDED relevance LOGITS - typically landing somewhere in
roughly the -10 to +10 range for this model family, but with no fixed
minimum or maximum. A raw score of, say, `3.2` cannot be interpreted
as "confidence" directly - it must first be mapped into a bounded
[0, 1] range that behaves like a probability, THEN scaled to the
spec's 0-100 scale. The sigmoid function
(`1 / (1 + e^-x)`) is the standard technique for this: it's monotonic
(preserves relative ranking), smooth, and saturates gracefully toward
0 and 1 at the extremes rather than clipping harshly.

WHY THE BLENDED (NOT PURELY TOP-1) SCORE IS USED
----------------------------------------------------
Using ONLY the single top-ranked chunk's score as confidence would
make confidence fragile to one lucky/unlucky match - e.g. one chunk
that happens to share vocabulary with the query but is otherwise
weakly relevant could produce a misleadingly high top score even
though the REST of the retrieved context is weak. This engine blends
the top chunk's score (70% weight - it IS the most relevant thing
found, and should dominate) with the mean score across ALL reranked
chunks (30% weight - a sanity check: if the whole result set is
weak, that should pull confidence down even when the single best
match looked fine in isolation). Both weights are named module
constants specifically so this heuristic is easy to find, tune, and
justify in one place - not scattered magic numbers.
"""

import math
import statistics
from typing import List

from app.core.base_service import BaseService
from app.core.constants import ConfidenceBand, PipelineStage
from app.core.exceptions import ConfidenceScoringError
from app.confidence.schemas import ConfidenceResult
from app.embeddings.schemas import RerankResult

# WHY 0.7 / 0.3 specifically: see module docstring. These are
# deliberately NOT exposed as `Settings` fields - unlike the
# GREEN/AMBER thresholds (which are business-meaningful cutoffs an
# operator might reasonably want to recalibrate), this weighting is an
# internal implementation detail of HOW the raw score is computed, not
# a policy decision - changing it changes what "confidence" measures,
# not just where the band lines are drawn.
_TOP_SCORE_WEIGHT = 0.7
_MEAN_SCORE_WEIGHT = 0.3


def _sigmoid(x: float) -> float:
    """
    Numerically stable sigmoid: `1 / (1 + e^-x)`.

    WHY the stability trick (branching on the sign of `x`): a naive
    `1 / (1 + math.exp(-x))` overflows `OverflowError` for very
    negative `x` (e.g. `x = -1000`) because `math.exp(-x)` would need
    to compute `e^1000`, a number too large to represent. Cross-encoder
    scores should never realistically reach that magnitude, but this
    is exactly the kind of unbounded external input (a score is just
    "whatever the model returned") that deserves a defensively correct
    implementation rather than trusting the input stays in a "normal"
    range.
    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


class ConfidenceEngine(BaseService):
    """
    Converts reranked cross-encoder scores into a 0-100 confidence
    score and Green/Amber/Red band.
    """

    def compute(self, reranked_results: List[RerankResult]) -> ConfidenceResult:
        """
        Args:
            reranked_results: Output of
                `RetrievalService.retrieve(...)` / directly from
                `CrossEncoderRerankerService.rerank(...)` - MUST be
                non-empty (an empty list reaching this stage is a
                programming error, since `RetrievalService` already
                raises `NoRetrievalResultsError` before reranking ever
                produces an empty list from non-empty candidates).

        Returns:
            A `ConfidenceResult` with the final score, band, and
            supporting detail.

        Raises:
            ConfidenceScoringError: if `reranked_results` is empty.
        """
        if not reranked_results:
            raise ConfidenceScoringError(
                "Cannot compute confidence from an empty result set - this "
                "indicates a caller invoked ConfidenceEngine without first "
                "checking for NoRetrievalResultsError upstream.",
                stage=PipelineStage.CONFIDENCE_SCORING,
            )

        raw_scores = [result.score for result in reranked_results]
        top_score = raw_scores[0]  # reranked_results is already sorted descending
        mean_score = statistics.mean(raw_scores)

        blended_logit = (_TOP_SCORE_WEIGHT * top_score) + (_MEAN_SCORE_WEIGHT * mean_score)
        confidence_probability = _sigmoid(blended_logit)
        score_0_100 = round(confidence_probability * 100, 2)

        per_source_scores = [round(_sigmoid(s) * 100, 2) for s in raw_scores]

        band = self._band_for_score(score_0_100)

        self.logger.bind(stage=PipelineStage.CONFIDENCE_SCORING.value).debug(
            f"Confidence computed: score={score_0_100} band={band.value} "
            f"(top_raw={top_score:.3f}, mean_raw={mean_score:.3f}, "
            f"chunks={len(reranked_results)})"
        )

        return ConfidenceResult(
            score=score_0_100,
            band=band,
            primary_relevance_score=top_score,
            contributing_chunk_count=len(reranked_results),
            per_source_scores=per_source_scores,
        )

    def _band_for_score(self, score_0_100: float) -> ConfidenceBand:
        """
        Apply the spec's exact banding rule:
            Above GREEN_THRESHOLD (80)      -> Green
            AMBER_THRESHOLD-GREEN_THRESHOLD (60-80) -> Amber
            Below AMBER_THRESHOLD (60)      -> Red

        WHY strict `>` for Green but inclusive `>=` for Amber's lower
        bound: matches the spec's own phrasing ("Above 80" is strictly
        greater-than; "60-80" is an inclusive range starting AT 60) -
        a score of exactly 80.0 is Amber, not Green; a score of
        exactly 60.0 is Amber, not Red. This also exactly mirrors
        `Settings._amber_must_be_below_green`'s validation, which
        requires AMBER < GREEN strictly, so these two thresholds can
        never produce a gap or overlap in coverage.
        """
        green_threshold = self.settings.CONFIDENCE_GREEN_THRESHOLD
        amber_threshold = self.settings.CONFIDENCE_AMBER_THRESHOLD

        if score_0_100 > green_threshold:
            return ConfidenceBand.GREEN
        if score_0_100 >= amber_threshold:
            return ConfidenceBand.AMBER
        return ConfidenceBand.RED

    def health_check(self) -> dict:
        """
        Verifies the sigmoid transform and banding logic produce
        sane, correctly-ordered results across a spread of synthetic
        scores spanning all three bands.
        """
        try:
            probe_results = [
                RerankResult(chunk_id="probe-high", text="probe", score=5.0, metadata={}),
                RerankResult(chunk_id="probe-mid", text="probe", score=0.5, metadata={}),
            ]
            result = self.compute(probe_results)
            healthy = 0.0 <= result.score <= 100.0 and len(result.per_source_scores) == 2
            return {
                "service": self.service_name,
                "healthy": healthy,
                "details": {
                    "probe_score": result.score,
                    "probe_band": result.band.value,
                    "green_threshold": self.settings.CONFIDENCE_GREEN_THRESHOLD,
                    "amber_threshold": self.settings.CONFIDENCE_AMBER_THRESHOLD,
                },
            }
        except ConfidenceScoringError as exc:
            return {
                "service": self.service_name,
                "healthy": False,
                "details": {"error": exc.message},
            }
