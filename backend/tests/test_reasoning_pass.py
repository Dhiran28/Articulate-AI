"""
Tests for ReasoningPass and its supporting pure functions (Sprint
4.5.1): the one component that now makes the one LLM call every
reasoning module's result comes from.

No real LLM call anywhere in this file — FakeLLMReasoner is the same
kind of in-memory stand-in test_llm_reasoner.py and (previously)
test_reasoning_modules.py used, satisfying the LLMReasoner Protocol
without touching PromptRegistry or a real provider.

See tests/README.md for how this file fits into the overall suite.
"""

import pytest

from app.analysis.models import AnalysisContext, MetricResult, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ReasoningResult, ResultMetadata
from app.analysis.reasoning_pass.batch import BatchedReasoningResult, ReasoningPass
from app.analysis.reasoning_pass.signals import compute_hedge_signal, extract_speaking_pace_hints
from app.llm.errors import LLMError, LLMSchemaError, LLMTimeoutError
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor


def _transcript(text: str = "So, I think the plan is solid and we should move forward with it."):
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


def _full_batch_result() -> BatchedReasoningResult:
    return BatchedReasoningResult(**{key: ReasoningResult(label="ok") for key in BatchedReasoningResult.model_fields})


class FakeLLMReasoner:
    """Records every (prompt_id, context) it's called with; returns a
    canned result or raises a canned LLMError."""

    def __init__(self, result: BatchedReasoningResult | None = None, error: LLMError | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def reason(self, prompt_id: str, context: dict, schema: type) -> BatchedReasoningResult:
        self.calls.append((prompt_id, context))
        if self._error is not None:
            raise self._error
        assert schema is BatchedReasoningResult
        return self._result if self._result is not None else _full_batch_result()


class TestReasoningPassHappyPath:
    async def test_returns_the_reasoners_validated_result(self) -> None:
        expected = _full_batch_result()
        reasoner = FakeLLMReasoner(result=expected)
        reasoning_pass = ReasoningPass(reasoner)

        result = await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

        assert result is expected

    async def test_calls_the_reasoner_exactly_once(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)

        await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

        assert len(reasoner.calls) == 1

    async def test_uses_its_own_prompt_id_by_default(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)

        await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

        prompt_id, _ = reasoner.calls[0]
        assert prompt_id == "reasoning_pass_v1"

    async def test_prompt_id_is_configurable(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner, prompt_id="reasoning_pass_v2")

        await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

        prompt_id, _ = reasoner.calls[0]
        assert prompt_id == "reasoning_pass_v2"

    async def test_transcript_text_reaches_the_template_context(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)
        transcript = _transcript(text="A very specific sentence about quarterly planning.")

        await reasoning_pass.run(AnalysisContext(transcript=transcript))

        _, template_context = reasoner.calls[0]
        assert "A very specific sentence about quarterly planning." in template_context["transcript"]

    async def test_hedge_signal_reaches_the_template_context(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)
        transcript = _transcript(text="I think maybe this is sort of right, I guess.")

        await reasoning_pass.run(AnalysisContext(transcript=transcript))

        _, template_context = reasoner.calls[0]
        assert template_context["hedge_word_count"] == "4"
        assert "maybe" in template_context["hedge_word_examples"]

    async def test_speaking_pace_hints_reach_the_template_context(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)
        pace_result = ModuleResult(
            metadata=ResultMetadata(module_name="speaking_pace", module_type=ModuleType.METRIC),
            status=ModuleStatus.OK,
            metric=MetricResult(value=142.0, unit="words_per_minute", details={"average_sentence_length": 9.5}),
        )
        context = AnalysisContext(transcript=_transcript(), metrics={"speaking_pace": pace_result})

        await reasoning_pass.run(context)

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] == "142.0"
        assert template_context["average_sentence_length"] == "9.5"

    async def test_missing_speaking_pace_falls_back_to_unknown_in_the_template_context(self) -> None:
        reasoner = FakeLLMReasoner()
        reasoning_pass = ReasoningPass(reasoner)

        await reasoning_pass.run(AnalysisContext(transcript=_transcript(), metrics={}))

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] == "unknown"
        assert template_context["average_sentence_length"] == "unknown"


class TestReasoningPassFailureModes:
    async def test_llm_error_propagates_uncaught(self) -> None:
        # ReasoningPass itself never catches an LLMError — translating a
        # batch failure into every reasoning module's ModuleResult is
        # ModuleRegistry's job (see test_analysis_engine.py), not this
        # class's. Keeping this class ignorant of ModuleResult/ModuleType
        # is what lets it stay a plain "prompt in, structured judgment
        # out" component with nothing analysis-domain-specific baked in.
        reasoner = FakeLLMReasoner(error=LLMTimeoutError("took too long"))
        reasoning_pass = ReasoningPass(reasoner)

        with pytest.raises(LLMTimeoutError):
            await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

    async def test_schema_error_propagates_uncaught(self) -> None:
        reasoner = FakeLLMReasoner(error=LLMSchemaError("missing fields"))
        reasoning_pass = ReasoningPass(reasoner)

        with pytest.raises(LLMSchemaError):
            await reasoning_pass.run(AnalysisContext(transcript=_transcript()))


class TestBatchedReasoningResultSchema:
    def test_has_exactly_the_six_expected_sections(self) -> None:
        assert set(BatchedReasoningResult.model_fields.keys()) == {
            "structure",
            "clarity",
            "logical_flow",
            "topic_drift",
            "confidence",
            "conciseness",
        }

    def test_every_section_is_a_plain_reasoning_result(self) -> None:
        # No numeric score field anywhere — this is what structurally
        # enforces "no scores" across all six dimensions in one place.
        for field in BatchedReasoningResult.model_fields.values():
            assert field.annotation is ReasoningResult

    def test_missing_a_section_fails_validation(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BatchedReasoningResult(
                structure=ReasoningResult(label="x"),
                clarity=ReasoningResult(label="x"),
                logical_flow=ReasoningResult(label="x"),
                topic_drift=ReasoningResult(label="x"),
                confidence=ReasoningResult(label="x"),
                # conciseness missing
            )


class TestComputeHedgeSignal:
    def test_counts_and_lists_hedge_phrases(self) -> None:
        count, examples = compute_hedge_signal("I think maybe this is sort of the right plan, I guess.")
        assert count == 4
        assert "maybe" in examples

    def test_no_hedges_reports_zero_and_none_found(self) -> None:
        count, examples = compute_hedge_signal("The plan is solid and we will proceed on schedule.")
        assert count == 0
        assert examples == "none found"

    def test_example_limit_caps_the_returned_examples(self) -> None:
        text = "I think, I guess, maybe, sort of, kind of, probably, might be, could be."
        count, examples = compute_hedge_signal(text, example_limit=2)
        assert count > 2
        assert len(examples.split(", ")) == 2


class TestExtractSpeakingPaceHints:
    def test_reads_words_per_minute_and_average_sentence_length(self) -> None:
        pace_result = ModuleResult(
            metadata=ResultMetadata(module_name="speaking_pace", module_type=ModuleType.METRIC),
            status=ModuleStatus.OK,
            metric=MetricResult(value=142.0, unit="words_per_minute", details={"average_sentence_length": 9.5}),
        )
        words_per_minute, average_sentence_length = extract_speaking_pace_hints({"speaking_pace": pace_result})
        assert words_per_minute == "142.0"
        assert average_sentence_length == "9.5"

    def test_returns_unknown_when_speaking_pace_is_absent(self) -> None:
        assert extract_speaking_pace_hints({}) == ("unknown", "unknown")

    def test_returns_unknown_when_speaking_pace_failed(self) -> None:
        failed_pace = ModuleResult(
            metadata=ResultMetadata(module_name="speaking_pace", module_type=ModuleType.METRIC),
            status=ModuleStatus.FAILED,
            error=ModuleErrorDetail(reason="metric_input_invalid", message="no duration"),
        )
        assert extract_speaking_pace_hints({"speaking_pace": failed_pace}) == ("unknown", "unknown")
