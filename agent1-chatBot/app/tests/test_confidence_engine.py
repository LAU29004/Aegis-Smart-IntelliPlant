"""
app/tests/test_confidence_engine.py

Unit tests for `app.confidence.confidence_engine.ConfidenceEngine` -
sigmoid-normalized scoring and Green/Amber/Red banding, per the
spec's explicit "Generate unit tests for ... Confidence" requirement.
"""

import pytest

from app.confidence.confidence_engine import ConfidenceEngine
from app.core.constants import ConfidenceBand
from app.core.exceptions import ConfidenceScoringError
from app.embeddings.schemas import RerankResult


@pytest.fixture
def confidence_engine(settings) -> ConfidenceEngine:
    return ConfidenceEngine(settings)


def _results(scores):
    return [RerankResult(chunk_id=f"c{i}", text="t", score=s, metadata={}) for i, s in enumerate(scores)]


class TestCompute:
    def test_strong_scores_produce_green_band(self, confidence_engine):
        result = confidence_engine.compute(_results([3.5, 3.0, 2.8]))
        assert result.band == ConfidenceBand.GREEN

    def test_moderate_scores_produce_amber_band(self, confidence_engine):
        result = confidence_engine.compute(_results([1.0, 0.8, 0.5]))
        assert result.band == ConfidenceBand.AMBER

    def test_weak_negative_scores_produce_red_band(self, confidence_engine):
        result = confidence_engine.compute(_results([-1.0, -2.0, -3.0]))
        assert result.band == ConfidenceBand.RED

    def test_score_is_bounded_between_zero_and_one_hundred(self, confidence_engine):
        result = confidence_engine.compute(_results([10.0, -10.0]))
        assert 0.0 <= result.score <= 100.0

    def test_per_source_scores_has_one_entry_per_input_chunk(self, confidence_engine):
        result = confidence_engine.compute(_results([1.0, 2.0, 3.0]))
        assert len(result.per_source_scores) == 3

    def test_contributing_chunk_count_matches_input(self, confidence_engine):
        result = confidence_engine.compute(_results([1.0, 2.0]))
        assert result.contributing_chunk_count == 2

    def test_primary_relevance_score_is_the_top_ranked_raw_score(self, confidence_engine):
        result = confidence_engine.compute(_results([4.2, 1.0]))
        assert result.primary_relevance_score == 4.2

    def test_empty_result_set_raises_confidence_scoring_error(self, confidence_engine):
        with pytest.raises(ConfidenceScoringError):
            confidence_engine.compute([])

    def test_extreme_negative_score_does_not_overflow(self, confidence_engine):
        result = confidence_engine.compute(_results([-600.0, -700.0]))
        assert result.score == 0.0

    def test_extreme_positive_score_does_not_overflow(self, confidence_engine):
        result = confidence_engine.compute(_results([600.0, 700.0]))
        assert result.score == 100.0


class TestBandBoundaries:
    """
    Verifies the EXACT boundary semantics from the spec: "Above 80"
    (strictly greater than) is Green; "60-80" (inclusive of 60) is
    Amber; "Below 60" is Red.
    """

    def test_exactly_at_green_threshold_is_amber_not_green(self, confidence_engine):
        assert confidence_engine._band_for_score(80.0) == ConfidenceBand.AMBER

    def test_just_above_green_threshold_is_green(self, confidence_engine):
        assert confidence_engine._band_for_score(80.01) == ConfidenceBand.GREEN

    def test_exactly_at_amber_threshold_is_amber_not_red(self, confidence_engine):
        assert confidence_engine._band_for_score(60.0) == ConfidenceBand.AMBER

    def test_just_below_amber_threshold_is_red(self, confidence_engine):
        assert confidence_engine._band_for_score(59.99) == ConfidenceBand.RED


class TestBlendingBehavior:
    def test_weak_supporting_chunks_pull_score_below_pure_top_match(self, confidence_engine):
        """A great top match with weak supporting chunks should score
        measurably lower than that same top match considered alone -
        confirming the 70/30 top/mean blend actually has an effect."""
        blended = confidence_engine.compute(_results([4.0, -3.0, -3.0]))
        top_only = confidence_engine.compute(_results([4.0]))
        assert blended.score < top_only.score


class TestHealthCheck:
    def test_health_check_reports_healthy(self, confidence_engine):
        result = confidence_engine.health_check()
        assert result["healthy"] is True
