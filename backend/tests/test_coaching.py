"""
Tests for the Coaching Engine and Communication Summary Generator
(Milestone 5): app/coaching/{engine,summary}.py.

No real LLM call anywhere in this file — FakeLLMReasoner is the same
in-memory stand-in pattern used throughout this codebase (see
test_reasoning_pass.py, test_llm_reasoner.py).

See tests/README.md for how this file fits into the overall suite.
"""

import pytest

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
from app.analysis.errors import AnalysisErrorReason
from app.coaching.engine import CoachingEngine
from app.coaching.errors import CoachingError, CoachingErrorReason
from app.coaching.models import CoachingContent, CoachingInsight, CoachingReport, Recommendation, SuggestedExercise
from app.coaching.summary import DASHBOARD_SUMMARY_MAX_LENGTH, CommunicationSummaryGenerator
from app.llm.errors import LLMSchemaError, LLMTimeoutError


def _content(**overrides) -> CoachingContent:
    defaults = dict(
        strengths=[CoachingInsight(message="Clear opening.", based_on_module="structure")],
        weaknesses=[CoachingInsight(message="Too many filler words.", based_on_module="filler_words")],
        recommendations=[
            Recommendation(message="Practice pausing instead of saying um.", based_on_module="filler_words", priority=1)
        ],
        suggested_exercises=[
            SuggestedExercise(title="Record and review", description="Record a 2-minute practice and review it.")
        ],
        next_practice_focus="Reduce filler words.",
        executive_summary="A solid, well-structured session with room to tighten delivery.",
    )
    defaults.update(overrides)
    return CoachingContent(**defaults)


class FakeLLMReasoner:
    def __init__(self, content: CoachingContent | None = None, error: Exception | None = None) -> None:
        self._content = content
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def reason(self, prompt_id: str, context: dict, schema: type) -> CoachingContent:
        self.calls.append((prompt_id, context))
        if self._error is not None:
            raise self._error
        assert schema is CoachingContent
        return self._content if self._content is not None else _content()


def _ok_metric(name: str) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=name, module_type=ModuleType.METRIC),
        status=ModuleStatus.OK,
        metric=MetricResult(value=1, unit="count", details={}),
    )


def _ok_reasoning(name: str) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=name, module_type=ModuleType.REASONING),
        status=ModuleStatus.OK,
        reasoning=ReasoningResult(label="ok"),
    )


def _failed(name: str) -> ModuleResult:
    return ModuleResult(
        metadata=ResultMetadata(module_name=name, module_type=ModuleType.METRIC),
        status=ModuleStatus.FAILED,
        error=ModuleErrorDetail(reason=AnalysisErrorReason.MODULE_ERROR, message="boom"),
    )


def _report_with(**modules: ModuleResult) -> AnalysisReport:
    report = AnalysisReport(transcript_id="t-1")
    report.modules.update(modules)
    return report


class TestCoachingEngineHappyPath:
    async def test_returns_a_coaching_report_from_the_llm_content(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"), structure=_ok_reasoning("structure"))

        result = await engine.generate(report)

        assert isinstance(result, CoachingReport)
        assert result.transcript_id == "t-1"
        assert result.next_practice_focus == "Reduce filler words."
        assert result.executive_summary

    async def test_calls_the_reasoner_exactly_once(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"))

        await engine.generate(report)

        assert len(reasoner.calls) == 1

    async def test_uses_the_coaching_v1_prompt_id_by_default(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)

        await engine.generate(_report_with(filler_words=_ok_metric("filler_words")))

        prompt_id, _ = reasoner.calls[0]
        assert prompt_id == "coaching_v1"

    async def test_never_receives_the_raw_transcript(self) -> None:
        # ADR 003 §5's structural guarantee: the coaching prompt is built
        # entirely from the AnalysisReport, never transcript text.
        # `session_id` (Milestone 5.1) is an intentional exception to
        # "only analysis_report_json" — it's a diagnostic, log-only key
        # (see app/llm/reasoner.py), not transcript content, and its
        # value here is just `report.transcript_id`.
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"))

        await engine.generate(report)

        _, template_context = reasoner.calls[0]
        assert set(template_context.keys()) == {"analysis_report_json", "session_id"}
        assert template_context["session_id"] == report.transcript_id

    async def test_only_ok_modules_reach_the_prompt(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"), hesitations=_failed("hesitations"))

        await engine.generate(report)

        _, template_context = reasoner.calls[0]
        assert '"filler_words"' in template_context["analysis_report_json"]
        assert '"hesitations"' not in template_context["analysis_report_json"]

    async def test_failed_modules_are_listed_as_unavailable(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"), hesitations=_failed("hesitations"))

        result = await engine.generate(report)

        assert any("hesitations" in item for item in result.unavailable)


class TestCoachingEngineFailureModes:
    async def test_nothing_to_coach_when_every_module_failed(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_failed("filler_words"))

        with pytest.raises(CoachingError) as exc_info:
            await engine.generate(report)

        assert exc_info.value.reason == CoachingErrorReason.NOTHING_TO_COACH

    async def test_nothing_to_coach_when_report_has_no_modules_at_all(self) -> None:
        reasoner = FakeLLMReasoner()
        engine = CoachingEngine(reasoner)

        with pytest.raises(CoachingError) as exc_info:
            await engine.generate(AnalysisReport(transcript_id="t-empty"))

        assert exc_info.value.reason == CoachingErrorReason.NOTHING_TO_COACH

    async def test_no_provider_configured_when_reasoner_is_none(self) -> None:
        engine = CoachingEngine(None)
        report = _report_with(filler_words=_ok_metric("filler_words"))

        with pytest.raises(CoachingError) as exc_info:
            await engine.generate(report)

        assert exc_info.value.reason == CoachingErrorReason.NO_PROVIDER_CONFIGURED

    async def test_llm_timeout_maps_to_coaching_error(self) -> None:
        reasoner = FakeLLMReasoner(error=LLMTimeoutError("too slow"))
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"))

        with pytest.raises(CoachingError) as exc_info:
            await engine.generate(report)

        assert exc_info.value.reason == CoachingErrorReason.LLM_TIMEOUT

    async def test_llm_schema_error_maps_to_coaching_error(self) -> None:
        reasoner = FakeLLMReasoner(error=LLMSchemaError("bad shape"))
        engine = CoachingEngine(reasoner)
        report = _report_with(filler_words=_ok_metric("filler_words"))

        with pytest.raises(CoachingError) as exc_info:
            await engine.generate(report)

        assert exc_info.value.reason == CoachingErrorReason.LLM_SCHEMA_ERROR


class TestCommunicationSummaryGenerator:
    def test_returns_the_executive_summary_unchanged_when_short(self) -> None:
        generator = CommunicationSummaryGenerator()
        report = CoachingReport(
            transcript_id="t-1",
            strengths=[],
            weaknesses=[],
            recommendations=[],
            suggested_exercises=[],
            next_practice_focus="x",
            executive_summary="A short summary.",
        )

        assert generator.generate(report) == "A short summary."

    def test_normalizes_internal_whitespace(self) -> None:
        generator = CommunicationSummaryGenerator()
        report = CoachingReport(
            transcript_id="t-1",
            strengths=[],
            weaknesses=[],
            recommendations=[],
            suggested_exercises=[],
            next_practice_focus="x",
            executive_summary="Line one.\n\n  Line   two.",
        )

        assert generator.generate(report) == "Line one. Line two."

    def test_truncates_long_summaries_on_a_word_boundary(self) -> None:
        generator = CommunicationSummaryGenerator()
        long_text = "word " * 200
        report = CoachingReport(
            transcript_id="t-1",
            strengths=[],
            weaknesses=[],
            recommendations=[],
            suggested_exercises=[],
            next_practice_focus="x",
            executive_summary=long_text,
        )

        result = generator.generate(report)

        assert len(result) <= DASHBOARD_SUMMARY_MAX_LENGTH + 1  # +1 for the ellipsis character
        assert result.endswith("…")
        assert not result[:-1].endswith(" ")
