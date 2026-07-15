"""
Tests for the six semantic Reasoning modules (Sprint 4.5): StructureModule,
ClarityModule, LogicalFlowModule, TopicDriftModule, ConfidenceModule,
ConcisenessModule, plus their shared orchestration in
app/analysis/modules/reasoning_base.py.

No real LLM call is made anywhere in this file. FakeLLMReasoner is a
plain in-memory stand-in satisfying the LLMReasoner Protocol
(app/llm/reasoner.py) — the same "fake the seam, not the internals"
approach test_llm_reasoner.py uses for LLMProvider and
test_transcription.py uses for TranscriptionProvider. Every reasoning
module is exercised only against this fake, never against
DefaultLLMReasoner or a real provider.

See tests/README.md for how this file fits into the overall suite.
"""

import pytest

from app.analysis.errors import AnalysisErrorReason
from app.analysis.models import (
    AnalysisContext,
    MetricResult,
    ModuleErrorDetail,
    ModuleResult,
    ModuleStatus,
    ModuleType,
    ReasoningResult,
    ResultMetadata,
)
from app.analysis.modules.base import AnalysisModule
from app.analysis.modules.clarity import ClarityModule
from app.analysis.modules.conciseness import ConcisenessModule
from app.analysis.modules.confidence import ConfidenceModule
from app.analysis.modules.logical_flow import LogicalFlowModule
from app.analysis.modules.structure import StructureModule
from app.analysis.modules.topic_drift import TopicDriftModule
from app.llm.errors import (
    LLMError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    NoProviderConfiguredError,
    PromptNotFoundError,
)
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor

ALL_MODULE_CLASSES = [
    StructureModule,
    ClarityModule,
    LogicalFlowModule,
    TopicDriftModule,
    ConfidenceModule,
    ConcisenessModule,
]

# LLMErrorReason and AnalysisErrorReason share identical string values
# (see app/analysis/errors.py's Sprint 4.5 comment) — this table is what
# reasoning_base.py's translation is expected to produce, one exception
# class at a time.
LLM_ERROR_TO_ANALYSIS_REASON = [
    (LLMTimeoutError, AnalysisErrorReason.LLM_TIMEOUT),
    (LLMProviderError, AnalysisErrorReason.LLM_PROVIDER_ERROR),
    (LLMInvalidResponseError, AnalysisErrorReason.LLM_INVALID_RESPONSE),
    (LLMSchemaError, AnalysisErrorReason.LLM_SCHEMA_ERROR),
    (PromptNotFoundError, AnalysisErrorReason.PROMPT_NOT_FOUND),
    (NoProviderConfiguredError, AnalysisErrorReason.NO_PROVIDER_CONFIGURED),
]


class FakeLLMReasoner:
    """
    Satisfies the LLMReasoner Protocol without touching PromptRegistry,
    PromptLoader, or any provider. Configured with either a canned
    ReasoningResult to return or an LLMError to raise, and records every
    (prompt_id, context) pair it was actually called with so tests can
    assert on what a module put into its own template context.
    """

    def __init__(self, result: ReasoningResult | None = None, error: LLMError | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def reason(self, prompt_id: str, context: dict, schema: type) -> ReasoningResult:
        self.calls.append((prompt_id, context))
        if self._error is not None:
            raise self._error
        assert schema is ReasoningResult  # every reasoning module uses the one shared schema
        return self._result if self._result is not None else ReasoningResult(label="ok")


def _transcript(text: str = "So, I think the plan is solid and we should move forward with it."):
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


def _context(transcript_result=None, metrics: dict | None = None) -> AnalysisContext:
    return AnalysisContext(
        transcript=transcript_result if transcript_result is not None else _transcript(),
        metrics=metrics or {},
    )


class TestInterfaceConformance:
    """Every reasoning module must satisfy the same AnalysisModule Protocol the Metric modules do."""

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    def test_satisfies_analysis_module_protocol(self, module_class) -> None:
        module = module_class(FakeLLMReasoner())
        assert isinstance(module, AnalysisModule)
        assert module.module_type == ModuleType.REASONING
        assert isinstance(module.metadata, dict)
        assert isinstance(module.module_name, str) and module.module_name

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    def test_module_names_are_unique(self, module_class) -> None:
        # A duplicate module_name across these six would silently break
        # ModuleRegistry registration (DuplicateModuleError) the moment
        # a real caller tries to register all six together.
        names = {m(FakeLLMReasoner()).module_name for m in ALL_MODULE_CLASSES}
        assert len(names) == len(ALL_MODULE_CLASSES)


class TestHappyPath:
    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_returns_an_ok_result_carrying_the_reasoner_output(self, module_class) -> None:
        reasoner = FakeLLMReasoner(result=ReasoningResult(label="clear", explanation="well organized"))
        module = module_class(reasoner)

        result = await module.analyze(_context())

        assert isinstance(result, ModuleResult)
        assert result.status == ModuleStatus.OK
        assert result.error is None
        assert result.metric is None
        assert result.reasoning == ReasoningResult(label="clear", explanation="well organized")
        assert result.metadata.module_name == module.module_name
        assert result.metadata.module_type == ModuleType.REASONING

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_calls_the_reasoner_with_its_own_prompt_id(self, module_class) -> None:
        reasoner = FakeLLMReasoner()
        module = module_class(reasoner)

        await module.analyze(_context())

        assert len(reasoner.calls) == 1
        prompt_id, _ = reasoner.calls[0]
        assert prompt_id == module.prompt_id

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_transcript_text_reaches_the_template_context(self, module_class) -> None:
        reasoner = FakeLLMReasoner()
        module = module_class(reasoner)
        transcript = _transcript(text="A very specific sentence about quarterly planning.")

        await module.analyze(_context(transcript_result=transcript))

        _, template_context = reasoner.calls[0]
        assert "A very specific sentence about quarterly planning." in template_context["transcript"]

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_never_produces_a_metric_or_a_score(self, module_class) -> None:
        # Structural guarantee, not just a convention: ReasoningResult
        # (models.py) has no numeric score field at all, so this is
        # really asserting the shared schema shape, but doing it via
        # every module's actual output keeps the guarantee end-to-end.
        reasoner = FakeLLMReasoner(result=ReasoningResult(label="x"))
        module = module_class(reasoner)

        result = await module.analyze(_context())

        assert result.metric is None
        assert not hasattr(result.reasoning, "score")


class TestErrorMapping:
    """
    Every LLMError subclass the shared LLMReasoner can raise must map to
    the matching AnalysisErrorReason, and the module must return a
    `failed` ModuleResult rather than let the exception propagate — the
    same per-module isolation ADR 003 §7 requires of Metric modules,
    now proven for Reasoning modules too.
    """

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    @pytest.mark.parametrize("error_class,expected_reason", LLM_ERROR_TO_ANALYSIS_REASON)
    async def test_llm_error_becomes_a_failed_module_result(self, module_class, error_class, expected_reason) -> None:
        reasoner = FakeLLMReasoner(error=error_class("boom"))
        module = module_class(reasoner)

        result = await module.analyze(_context())

        assert result.status == ModuleStatus.FAILED
        assert result.reasoning is None
        assert result.metric is None
        assert result.error is not None
        assert result.error.reason == expected_reason
        assert result.error.message == "boom"

    async def test_a_non_llm_exception_still_propagates(self) -> None:
        # reasoning_base.py only catches LLMError — anything else is a
        # genuine bug and should surface, not be silently swallowed as
        # if it were a classified LLM failure. (ModuleRegistry, not this
        # class, is what converts an unexpected exception into a
        # MODULE_ERROR result — see test_analysis_engine.py's
        # TestModuleFailureIsolation.)
        class ExplodingReasoner:
            async def reason(self, prompt_id, context, schema):
                raise RuntimeError("not an LLMError at all")

        module = StructureModule(ExplodingReasoner())
        with pytest.raises(RuntimeError):
            await module.analyze(_context())


class TestConfidenceModuleHedgeSignal:
    """
    ConfidenceModule's one piece of module-specific logic: a local,
    deterministic hedge-word count computed without any LLM call, fed
    into the prompt as extra context.
    """

    async def test_hedge_words_are_counted_and_passed_to_the_prompt(self) -> None:
        reasoner = FakeLLMReasoner()
        module = ConfidenceModule(reasoner)
        transcript = _transcript(text="I think maybe this is sort of the right plan, I guess.")

        await module.analyze(_context(transcript_result=transcript))

        _, template_context = reasoner.calls[0]
        assert template_context["hedge_word_count"] == "4"  # "I think", "maybe", "sort of", "I guess"
        assert "maybe" in template_context["hedge_word_examples"]

    async def test_no_hedges_reports_zero_and_none_found(self) -> None:
        reasoner = FakeLLMReasoner()
        module = ConfidenceModule(reasoner)
        transcript = _transcript(text="The plan is solid and we will proceed on schedule.")

        await module.analyze(_context(transcript_result=transcript))

        _, template_context = reasoner.calls[0]
        assert template_context["hedge_word_count"] == "0"
        assert template_context["hedge_word_examples"] == "none found"

    async def test_hedge_count_never_appears_in_the_returned_result(self) -> None:
        # The sub-signal is prompt context only — it must never leak into
        # the module's actual output, which stays a plain ReasoningResult.
        reasoner = FakeLLMReasoner(result=ReasoningResult(label="confident"))
        module = ConfidenceModule(reasoner)
        transcript = _transcript(text="I think maybe this is sort of right.")

        result = await module.analyze(_context(transcript_result=transcript))

        assert result.reasoning == ReasoningResult(label="confident")


class TestConcisenessModuleMetricHints:
    """
    ConcisenessModule's one piece of module-specific logic: reading
    context.metrics (populated by ModuleRegistry's two-phase execution,
    see registry.py) for speaking_pace's already-computed figures, and
    degrading gracefully when that metric didn't run or failed.
    """

    def _speaking_pace_result(self, *, words_per_minute=142.0, average_sentence_length=9.5) -> ModuleResult:
        return ModuleResult(
            metadata=ResultMetadata(module_name="speaking_pace", module_type=ModuleType.METRIC),
            status=ModuleStatus.OK,
            metric=MetricResult(
                value=words_per_minute,
                unit="words_per_minute",
                details={"average_sentence_length": average_sentence_length},
            ),
        )

    async def test_uses_speaking_pace_metrics_when_present(self) -> None:
        reasoner = FakeLLMReasoner()
        module = ConcisenessModule(reasoner)
        context = _context(metrics={"speaking_pace": self._speaking_pace_result()})

        await module.analyze(context)

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] == "142.0"
        assert template_context["average_sentence_length"] == "9.5"

    async def test_falls_back_to_unknown_when_speaking_pace_did_not_run(self) -> None:
        reasoner = FakeLLMReasoner()
        module = ConcisenessModule(reasoner)

        await module.analyze(_context(metrics={}))

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] == "unknown"
        assert template_context["average_sentence_length"] == "unknown"

    async def test_falls_back_to_unknown_when_speaking_pace_failed(self) -> None:
        reasoner = FakeLLMReasoner()
        module = ConcisenessModule(reasoner)
        failed_pace = ModuleResult(
            metadata=ResultMetadata(module_name="speaking_pace", module_type=ModuleType.METRIC),
            status=ModuleStatus.FAILED,
            error=ModuleErrorDetail(reason=AnalysisErrorReason.METRIC_INPUT_INVALID, message="no duration"),
        )

        await module.analyze(_context(metrics={"speaking_pace": failed_pace}))

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] == "unknown"

    async def test_never_calls_speaking_pace_module_itself(self) -> None:
        # ConcisenessModule only reads the already-populated
        # context.metrics dict — it has no reference to SpeakingPaceModule
        # at all, so there is nothing to call even if it wanted to. This
        # test documents that architectural guarantee via absence: the
        # module works fine given only a plain dict, never a real module.
        reasoner = FakeLLMReasoner()
        module = ConcisenessModule(reasoner)
        assert not hasattr(module, "speaking_pace_module")
        assert not hasattr(module, "_speaking_pace")
        await module.analyze(_context(metrics={"speaking_pace": self._speaking_pace_result()}))
