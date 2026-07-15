"""
Tests for the six section-reading Reasoning modules (Sprint 4.5.1):
StructureModule, ClarityModule, LogicalFlowModule, TopicDriftModule,
ConfidenceModule, ConcisenessModule.

Sprint 4.5.1 changed what these modules do: none of them call an LLM or
build a prompt anymore (that's `ReasoningPass`'s job now — see
test_reasoning_pass.py). Each one just reads its own section out of a
`BatchedReasoningResult` that's expected to already be sitting in
`AnalysisContext.reasoning_context[REASONING_PASS_RESULT_KEY]` — so
these tests exercise that read-and-wrap logic directly, with no fake
LLM anywhere in this file at all.

See tests/README.md for how this file fits into the overall suite.
"""

import pytest

from app.analysis.errors import AnalysisErrorReason
from app.analysis.models import AnalysisContext, ModuleStatus, ModuleType, ReasoningResult
from app.analysis.modules.base import AnalysisModule
from app.analysis.modules.clarity import ClarityModule
from app.analysis.modules.conciseness import ConcisenessModule
from app.analysis.modules.confidence import ConfidenceModule
from app.analysis.modules.logical_flow import LogicalFlowModule
from app.analysis.modules.section_reasoning_base import REASONING_PASS_RESULT_KEY
from app.analysis.modules.structure import StructureModule
from app.analysis.modules.topic_drift import TopicDriftModule
from app.analysis.reasoning_pass.batch import BatchedReasoningResult
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


def _transcript(text: str = "So, I think the plan is solid and we should move forward with it."):
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


def _batch(**overrides: ReasoningResult) -> BatchedReasoningResult:
    """A fully-populated BatchedReasoningResult, each section defaulting
    to a distinct, easily-asserted-on label unless overridden."""
    defaults = {key: ReasoningResult(label=f"{key}_label") for key in BatchedReasoningResult.model_fields}
    defaults.update(overrides)
    return BatchedReasoningResult(**defaults)


def _context(*, batch: BatchedReasoningResult | None = None, transcript_result=None) -> AnalysisContext:
    reasoning_context = {} if batch is None else {REASONING_PASS_RESULT_KEY: batch}
    return AnalysisContext(
        transcript=transcript_result if transcript_result is not None else _transcript(),
        reasoning_context=reasoning_context,
    )


class TestInterfaceConformance:
    """Every reasoning module must satisfy the same AnalysisModule Protocol the Metric modules do."""

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    def test_satisfies_analysis_module_protocol(self, module_class) -> None:
        module = module_class()
        assert isinstance(module, AnalysisModule)
        assert module.module_type == ModuleType.REASONING
        assert isinstance(module.metadata, dict)
        assert isinstance(module.module_name, str) and module.module_name

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    def test_no_longer_requires_an_llm_reasoner_to_construct(self, module_class) -> None:
        # Sprint 4.5.1's whole point: these modules don't call an LLM
        # themselves anymore, so constructing one takes no arguments at
        # all now (contrast with Sprint 4.5's `module_class(reasoner)`).
        module = module_class()
        assert not hasattr(module, "_reasoner")

    def test_module_names_are_unique(self) -> None:
        names = {m().module_name for m in ALL_MODULE_CLASSES}
        assert len(names) == len(ALL_MODULE_CLASSES)

    def test_every_module_names_a_real_batched_reasoning_result_field(self) -> None:
        # section_key must always resolve to a real field on
        # BatchedReasoningResult, or every one of these modules would
        # silently fail at runtime — checked once, structurally, here.
        for module_class in ALL_MODULE_CLASSES:
            module = module_class()
            assert module.section_key in BatchedReasoningResult.model_fields


class TestHappyPath:
    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_returns_its_own_section_of_the_batched_result(self, module_class) -> None:
        module = module_class()
        expected_section = ReasoningResult(label="a_specific_label", explanation="specific explanation")
        batch = _batch(**{module.section_key: expected_section})

        result = await module.analyze(_context(batch=batch))

        assert result.status == ModuleStatus.OK
        assert result.error is None
        assert result.metric is None
        assert result.reasoning == expected_section
        assert result.metadata.module_name == module.module_name
        assert result.metadata.module_type == ModuleType.REASONING

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_does_not_leak_another_modules_section(self, module_class) -> None:
        module = module_class()
        own_section = ReasoningResult(label="mine")
        batch = _batch(**{module.section_key: own_section})
        # Every other section is deliberately given a different label —
        # if a module ever read the wrong field, this would catch it.
        for key in BatchedReasoningResult.model_fields:
            if key != module.section_key:
                assert getattr(batch, key).label != "mine"

        result = await module.analyze(_context(batch=batch))

        assert result.reasoning.label == "mine"

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_never_produces_a_metric_or_a_score(self, module_class) -> None:
        module = module_class()
        result = await module.analyze(_context(batch=_batch()))

        assert result.metric is None
        assert not hasattr(result.reasoning, "score")


class TestNoReasoningPassResultAvailable:
    """
    The registry only calls a REASONING module's analyze() at all once a
    batched result is ready (see registry.py) — but a module is still
    expected to fail gracefully, not crash, if it's ever invoked
    directly without one (e.g. a stray unit test, or future misuse).
    """

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_missing_batch_result_is_a_failed_result_not_a_crash(self, module_class) -> None:
        module = module_class()

        result = await module.analyze(_context(batch=None))

        assert result.status == ModuleStatus.FAILED
        assert result.reasoning is None
        assert result.error.reason == AnalysisErrorReason.NO_PROVIDER_CONFIGURED

    @pytest.mark.parametrize("module_class", ALL_MODULE_CLASSES)
    async def test_wrong_type_in_the_reasoning_context_slot_is_a_failed_result(self, module_class) -> None:
        module = module_class()
        context = AnalysisContext(
            transcript=_transcript(),
            reasoning_context={REASONING_PASS_RESULT_KEY: "not a BatchedReasoningResult"},
        )

        result = await module.analyze(context)

        assert result.status == ModuleStatus.FAILED
        assert result.error.reason == AnalysisErrorReason.LLM_SCHEMA_ERROR
