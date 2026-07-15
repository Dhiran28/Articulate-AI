"""
Tests for the Overall Communication Score (Milestone 5):
app/scoring/{weights,dimension_scores,engine}.py.

See tests/README.md for how this file fits into the overall suite, and
app/scoring/README.md for the algorithm's own documentation.
"""

import pytest

from app.analysis.errors import AnalysisErrorReason
from app.analysis.models import (
    AnalysisReport,
    MetricResult,
    ModuleErrorDetail,
    ModuleResult,
    ModuleStatus,
    ModuleType,
    ReasoningResult,
    ResultMetadata,
)
from app.scoring.dimension_scores import (
    score_filler_words,
    score_hesitations,
    score_reasoning_dimension,
    score_repetitions,
    score_speaking_pace,
)
from app.scoring.engine import ScoringEngine
from app.scoring.errors import ScoringError, ScoringErrorReason
from app.scoring.models import ScoreBand
from app.scoring.weights import MODULE_WEIGHTS


def _metric_result(module_name: str, value, unit: str = "count", details: dict | None = None) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=module_name, module_type=ModuleType.METRIC),
        status=ModuleStatus.OK,
        metric=MetricResult(value=value, unit=unit, details=details or {}),
    )


def _reasoning_result(module_name: str, label: str) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=module_name, module_type=ModuleType.REASONING),
        status=ModuleStatus.OK,
        reasoning=ReasoningResult(label=label),
    )


def _failed_result(module_name: str, module_type: ModuleType = ModuleType.METRIC) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=module_name, module_type=module_type),
        status=ModuleStatus.FAILED,
        error=ModuleErrorDetail(reason=AnalysisErrorReason.MODULE_ERROR, message="boom"),
    )


def _perfect_report(transcript_id: str = "t-1") -> AnalysisReport:
    """Every one of the ten weighted modules present, each scoring 100."""
    report = AnalysisReport(transcript_id=transcript_id)
    report.modules["filler_words"] = _metric_result("filler_words", 0, "count", {"frequency_per_100_words": 0.0})
    report.modules["hesitations"] = _metric_result("hesitations", 0, "count", {"long_pauses": []})
    report.modules["repetitions"] = _metric_result("repetitions", 0)
    report.modules["speaking_pace"] = _metric_result("speaking_pace", 140.0, "words_per_minute")
    report.modules["structure"] = _reasoning_result("structure", "clear_structure")
    report.modules["clarity"] = _reasoning_result("clarity", "clear")
    report.modules["logical_flow"] = _reasoning_result("logical_flow", "coherent_flow")
    report.modules["topic_drift"] = _reasoning_result("topic_drift", "on_topic")
    report.modules["confidence"] = _reasoning_result("confidence", "confident")
    report.modules["conciseness"] = _reasoning_result("conciseness", "concise")
    return report


class TestWeights:
    def test_weights_sum_to_100(self) -> None:
        assert abs(sum(MODULE_WEIGHTS.values()) - 100.0) < 1e-9

    def test_every_weighted_module_has_a_documented_weight(self) -> None:
        assert set(MODULE_WEIGHTS.keys()) == {
            "structure",
            "logical_flow",
            "clarity",
            "topic_drift",
            "confidence",
            "conciseness",
            "filler_words",
            "hesitations",
            "repetitions",
            "speaking_pace",
        }

    def test_structural_thinking_tier_outweighs_fluency_tier(self) -> None:
        # The one non-arbitrary anchor this algorithm has: the product's
        # stated mission ("structural thinking, not grammar") implies
        # this exact ordering — see weights.py's module docstring.
        assert MODULE_WEIGHTS["structure"] > MODULE_WEIGHTS["confidence"] > MODULE_WEIGHTS["filler_words"]


class TestDimensionScoreFunctions:
    def test_zero_fillers_scores_100(self) -> None:
        result = _metric_result("filler_words", 0, details={"frequency_per_100_words": 0.0})
        score, driver = score_filler_words(result)
        assert score == 100.0
        assert "0.0" in driver

    def test_fillers_at_ceiling_scores_0(self) -> None:
        result = _metric_result("filler_words", 10, details={"frequency_per_100_words": 10.0})
        score, _ = score_filler_words(result)
        assert score == 0.0

    def test_fillers_halfway_scores_50(self) -> None:
        result = _metric_result("filler_words", 5, details={"frequency_per_100_words": 5.0})
        score, _ = score_filler_words(result)
        assert score == 50.0

    def test_no_pauses_scores_100(self) -> None:
        result = _metric_result("hesitations", 0, details={"long_pauses": []})
        score, driver = score_hesitations(result)
        assert score == 100.0
        assert "no pauses" in driver

    def test_all_pauses_long_scores_0(self) -> None:
        result = _metric_result("hesitations", 3, details={"long_pauses": [{}, {}, {}]})
        score, _ = score_hesitations(result)
        assert score == 0.0

    def test_half_pauses_long_scores_50(self) -> None:
        result = _metric_result("hesitations", 4, details={"long_pauses": [{}, {}]})
        score, _ = score_hesitations(result)
        assert score == 50.0

    def test_zero_repetitions_scores_100(self) -> None:
        result = _metric_result("repetitions", 0)
        score, _ = score_repetitions(result)
        assert score == 100.0

    def test_repetitions_at_ceiling_scores_0(self) -> None:
        result = _metric_result("repetitions", 8)
        score, _ = score_repetitions(result)
        assert score == 0.0

    @pytest.mark.parametrize("wpm", [120.0, 140.0, 160.0])
    def test_ideal_pace_range_scores_100(self, wpm: float) -> None:
        result = _metric_result("speaking_pace", wpm, "words_per_minute")
        score, _ = score_speaking_pace(result)
        assert score == 100.0

    def test_pace_at_floor_scores_0(self) -> None:
        result = _metric_result("speaking_pace", 80.0, "words_per_minute")
        score, _ = score_speaking_pace(result)
        assert score == 0.0

    def test_pace_at_ceiling_scores_0(self) -> None:
        result = _metric_result("speaking_pace", 200.0, "words_per_minute")
        score, _ = score_speaking_pace(result)
        assert score == 0.0

    def test_pace_below_floor_clamps_to_0_not_negative(self) -> None:
        result = _metric_result("speaking_pace", 20.0, "words_per_minute")
        score, _ = score_speaking_pace(result)
        assert score == 0.0

    def test_recognized_reasoning_label_maps_to_its_band(self) -> None:
        result = _reasoning_result("structure", "partial_structure")
        score, driver = score_reasoning_dimension("structure", result)
        assert score == 60.0
        assert driver == "partial_structure"

    def test_unrecognized_reasoning_label_falls_back_to_neutral(self) -> None:
        result = _reasoning_result("structure", "something_the_model_made_up")
        score, driver = score_reasoning_dimension("structure", result)
        assert score == 60.0
        assert "unrecognized label" in driver


class TestScoringEngine:
    def test_a_perfect_report_scores_100(self) -> None:
        engine = ScoringEngine()
        score = engine.score(_perfect_report())
        assert score.overall_score == 100.0
        assert score.band == ScoreBand.EXCELLENT
        assert score.unscored_modules == []
        assert len(score.module_scores) == 10

    def test_effective_weights_sum_to_100_when_everything_succeeds(self) -> None:
        engine = ScoringEngine()
        score = engine.score(_perfect_report())
        assert abs(sum(m.effective_weight for m in score.module_scores) - 100.0) < 1e-9

    def test_a_missing_module_is_excluded_and_weight_is_redistributed(self) -> None:
        report = _perfect_report()
        del report.modules["structure"]  # never ran at all

        engine = ScoringEngine()
        score = engine.score(report)

        assert "structure" in score.unscored_modules
        assert len(score.module_scores) == 9
        assert abs(sum(m.effective_weight for m in score.module_scores) - 100.0) < 1e-9
        # Every remaining module still scores 100, so the overall score
        # is unaffected by the exclusion once weights are renormalized.
        assert score.overall_score == 100.0

    def test_a_failed_module_is_excluded_the_same_way_as_missing(self) -> None:
        report = _perfect_report()
        report.modules["filler_words"] = _failed_result("filler_words")

        engine = ScoringEngine()
        score = engine.score(report)

        assert "filler_words" in score.unscored_modules
        assert not any(m.module_name == "filler_words" for m in score.module_scores)

    def test_a_reasoning_module_failure_does_not_zero_the_score(self) -> None:
        report = _perfect_report()
        for name in ("structure", "clarity", "logical_flow", "topic_drift", "confidence", "conciseness"):
            report.modules[name] = _failed_result(name, ModuleType.REASONING)

        engine = ScoringEngine()
        score = engine.score(report)

        # Only the four Metric modules remain, all perfect.
        assert len(score.module_scores) == 4
        assert score.overall_score == 100.0

    def test_no_scorable_modules_raises(self) -> None:
        report = AnalysisReport(transcript_id="t-empty")
        engine = ScoringEngine()

        with pytest.raises(ScoringError) as exc_info:
            engine.score(report)

        assert exc_info.value.reason == ScoringErrorReason.NO_SCORABLE_MODULES

    def test_worst_case_report_scores_low_and_needs_work(self) -> None:
        report = AnalysisReport(transcript_id="t-1")
        report.modules["filler_words"] = _metric_result(
            "filler_words", 10, details={"frequency_per_100_words": 10.0}
        )
        report.modules["hesitations"] = _metric_result("hesitations", 4, details={"long_pauses": [{}, {}, {}, {}]})
        report.modules["repetitions"] = _metric_result("repetitions", 8)
        report.modules["speaking_pace"] = _metric_result("speaking_pace", 200.0, "words_per_minute")
        for name in ("structure", "clarity", "logical_flow", "topic_drift", "confidence", "conciseness"):
            label = {
                "structure": "no_structure",
                "clarity": "unclear",
                "logical_flow": "disjointed",
                "topic_drift": "significant_drift",
                "confidence": "uncertain",
                "conciseness": "verbose",
            }[name]
            report.modules[name] = _reasoning_result(name, label)

        engine = ScoringEngine()
        score = engine.score(report)

        # All four metrics bottom out at 0 (weight 6.25 each = 25 total);
        # all six reasoning dimensions bottom out at 20 (weights 45 + 30
        # = 75 total). Weighted: (75 * 20 + 25 * 0) / 100 = 15.0.
        assert score.overall_score == 15.0
        assert score.band == ScoreBand.NEEDS_WORK

    def test_module_scores_expose_full_transparency(self) -> None:
        # Every field a caller would need to audit *why* the overall
        # score came out the way it did, without re-deriving anything.
        engine = ScoringEngine()
        score = engine.score(_perfect_report())

        for module_score in score.module_scores:
            assert module_score.module_name
            assert 0.0 <= module_score.score <= 100.0
            assert module_score.nominal_weight > 0
            assert module_score.effective_weight > 0
            assert module_score.driver
