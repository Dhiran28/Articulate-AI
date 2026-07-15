"""
Tests for the Communication Intelligence Engine's foundation (Sprint 4.2):
ModuleRegistry (registration, duplicate prevention, execution order) and
AnalysisEngine (empty-registry behaviour, the empty-transcript guard, and
per-module failure isolation).

See tests/README.md for how this file fits into the overall suite. No
real analysis modules exist yet (Sprint 4.2 explicitly excludes them) —
every module here is a small fake built just for these tests, the same
approach test_transcription.py uses for TranscriptionProvider.
"""

import pytest

from app.analysis.engine import AnalysisEngine
from app.analysis.errors import AnalysisError, AnalysisErrorReason
from app.analysis.models import (
    MetricResult,
    ModuleResult,
    ModuleStatus,
    ModuleType,
    ReasoningResult,
    ResultMetadata,
)
from app.analysis.modules.clarity import ClarityModule
from app.analysis.modules.conciseness import ConcisenessModule
from app.analysis.modules.confidence import ConfidenceModule
from app.analysis.modules.logical_flow import LogicalFlowModule
from app.analysis.modules.structure import StructureModule
from app.analysis.modules.topic_drift import TopicDriftModule
from app.analysis.reasoning_pass.batch import BatchedReasoningResult, ReasoningPass
from app.analysis.registry import DuplicateModuleError, ModuleRegistry
from app.llm.errors import LLMTimeoutError
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor

ALL_SIX_REASONING_MODULE_CLASSES = [
    StructureModule,
    ClarityModule,
    LogicalFlowModule,
    TopicDriftModule,
    ConfidenceModule,
    ConcisenessModule,
]


def _full_batch_result() -> BatchedReasoningResult:
    return BatchedReasoningResult(**{key: ReasoningResult(label="ok") for key in BatchedReasoningResult.model_fields})


class FakeReasoningPassLLMReasoner:
    """Records every call; returns a canned BatchedReasoningResult or raises a canned LLMError."""

    def __init__(self, result: BatchedReasoningResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def reason(self, prompt_id: str, context: dict, schema: type) -> BatchedReasoningResult:
        self.calls.append((prompt_id, context))
        if self._error is not None:
            raise self._error
        return self._result if self._result is not None else _full_batch_result()


def _transcript(text: str = "So, um, I think the plan is solid and we should move forward with it."):
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


class FakeMetricModule:
    """A minimal, real AnalysisModule — no scoring logic, just enough to
    exercise the registry/engine machinery."""

    def __init__(self, module_name: str = "fake_metric") -> None:
        self.module_name = module_name
        self.module_type = ModuleType.METRIC
        self.metadata: dict = {"version": "0.1.0"}

    async def analyze(self, context) -> ModuleResult:
        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            metric=MetricResult(value=120, unit="words_per_minute"),
        )


class FakeReasoningModule:
    def __init__(self, module_name: str = "fake_reasoning") -> None:
        self.module_name = module_name
        self.module_type = ModuleType.REASONING
        self.metadata: dict = {}

    async def analyze(self, context) -> ModuleResult:
        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            reasoning=ReasoningResult(label="ok"),
        )


class FakeCrashingModule:
    def __init__(self, module_name: str = "fake_crasher") -> None:
        self.module_name = module_name
        self.module_type = ModuleType.METRIC
        self.metadata: dict = {}

    async def analyze(self, context) -> ModuleResult:
        raise RuntimeError("boom")


class TestModuleRegistration:
    def test_register_adds_a_module(self) -> None:
        registry = ModuleRegistry()
        module = FakeMetricModule()

        registry.register(module)

        assert len(registry) == 1
        assert "fake_metric" in registry
        assert registry.get("fake_metric") is module

    def test_discover_returns_every_registered_module(self) -> None:
        registry = ModuleRegistry()
        a, b = FakeMetricModule("a"), FakeReasoningModule("b")
        registry.register(a)
        registry.register(b)

        assert registry.discover() == [a, b]

    def test_get_returns_none_for_an_unknown_name(self) -> None:
        registry = ModuleRegistry()
        assert registry.get("does_not_exist") is None

    def test_clear_removes_every_registered_module(self) -> None:
        registry = ModuleRegistry()
        registry.register(FakeMetricModule())

        registry.clear()

        assert len(registry) == 0
        assert registry.discover() == []


class TestDuplicatePrevention:
    def test_registering_the_same_name_twice_raises(self) -> None:
        registry = ModuleRegistry()
        registry.register(FakeMetricModule("dup"))

        with pytest.raises(DuplicateModuleError):
            registry.register(FakeReasoningModule("dup"))

    def test_a_rejected_duplicate_does_not_replace_the_original(self) -> None:
        registry = ModuleRegistry()
        original = FakeMetricModule("dup")
        registry.register(original)

        with pytest.raises(DuplicateModuleError):
            registry.register(FakeReasoningModule("dup"))

        # The original registration is untouched — a failed registration
        # attempt must not have side effects on the registry's state.
        assert registry.get("dup") is original
        assert len(registry) == 1


class TestExecutionOrder:
    async def test_metric_modules_run_before_reasoning_modules_regardless_of_registration_order(self) -> None:
        # Sprint 4.5 change: execution is two-phase, not flat registration
        # order (see registry.py's execute()). Every METRIC module runs
        # first (in registration order among themselves), then every
        # REASONING module runs (in registration order among themselves)
        # — so registering metric/reasoning/metric produces
        # metric,metric,reasoning, not the flat registration order.
        registry = ModuleRegistry()
        registry.register(FakeMetricModule("first"))
        registry.register(FakeReasoningModule("second"))
        registry.register(FakeMetricModule("third"))

        results = await registry.execute(_transcript())

        assert [r.metadata.module_name for r in results] == ["first", "third", "second"]

    async def test_registration_order_is_preserved_within_each_phase(self) -> None:
        registry = ModuleRegistry()
        registry.register(FakeReasoningModule("r1"))
        registry.register(FakeMetricModule("m1"))
        registry.register(FakeReasoningModule("r2"))
        registry.register(FakeMetricModule("m2"))

        results = await registry.execute(_transcript())

        assert [r.metadata.module_name for r in results] == ["m1", "m2", "r1", "r2"]

    async def test_report_preserves_registration_order(self) -> None:
        registry = ModuleRegistry()
        registry.register(FakeMetricModule("z_module"))
        registry.register(FakeMetricModule("a_module"))
        engine = AnalysisEngine(registry=registry)

        report = await engine.run("t-1", _transcript())

        # Insertion order, not alphabetical or any other implicit sort.
        assert list(report.modules.keys()) == ["z_module", "a_module"]


class TestEmptyRegistryBehaviour:
    async def test_empty_registry_returns_an_empty_but_valid_report(self) -> None:
        engine = AnalysisEngine(registry=ModuleRegistry())

        report = await engine.run("t-1", _transcript())

        assert report.transcript_id == "t-1"
        assert report.modules == {}

    async def test_empty_transcript_guard_fires_even_with_an_empty_registry(self) -> None:
        # The guard is a property of the input, not of what's registered
        # — it must fire regardless of whether there's anything to run.
        engine = AnalysisEngine(registry=ModuleRegistry())

        with pytest.raises(AnalysisError) as exc_info:
            await engine.run("t-1", _transcript(text="hi"))

        assert exc_info.value.reason == AnalysisErrorReason.TRANSCRIPT_EMPTY


class TestModuleFailureIsolation:
    async def test_a_crashing_module_does_not_affect_the_others(self) -> None:
        # A ReasoningPass is configured so "healthy_two" (a REASONING-type
        # fake) actually gets to run at all under Sprint 4.5.1's registry
        # — otherwise it would fail with NO_PROVIDER_CONFIGURED before
        # this test ever exercises the crash-isolation behavior it's
        # actually testing.
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(FakeReasoningPassLLMReasoner()))
        registry.register(FakeMetricModule("healthy_one"))
        registry.register(FakeCrashingModule("crasher"))
        registry.register(FakeReasoningModule("healthy_two"))
        engine = AnalysisEngine(registry=registry)

        report = await engine.run("t-1", _transcript())

        assert report.modules["healthy_one"].status == ModuleStatus.OK
        assert report.modules["healthy_two"].status == ModuleStatus.OK
        assert report.modules["crasher"].status == ModuleStatus.FAILED
        assert report.modules["crasher"].error.reason == AnalysisErrorReason.MODULE_ERROR


class FakeContextReadingModule:
    """
    A REASONING fake that reports back what it actually received in its
    AnalysisContext, so tests can assert on the *contents* the registry
    hands a module, not just that it ran.
    """

    def __init__(self, module_name: str = "context_reader") -> None:
        self.module_name = module_name
        self.module_type = ModuleType.REASONING
        self.metadata: dict = {}

    async def analyze(self, context) -> ModuleResult:
        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            reasoning=ReasoningResult(
                label="ok",
                explanation=f"saw {sorted(context.metrics.keys())}",
            ),
        )


class TestAnalysisContextPropagation:
    """
    Sprint 4.5: every module now receives an AnalysisContext, not a bare
    transcript, and the registry's two-phase execution is what makes
    `context.metrics` meaningful for a REASONING module.
    """

    async def test_a_reasoning_module_receives_completed_metric_results(self) -> None:
        # Sprint 4.5.1: a REASONING-type module only has its analyze()
        # called at all once a ReasoningPass is configured and succeeds
        # (see TestReasoningPassIntegration) — a plain fake reasoning
        # module needs one wired up here too, even though this fake
        # itself never reads the batched result.
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(FakeReasoningPassLLMReasoner()))
        registry.register(FakeMetricModule("fake_metric"))
        registry.register(FakeContextReadingModule("reader"))

        results = await registry.execute(_transcript())

        reader_result = next(r for r in results if r.metadata.module_name == "reader")
        assert reader_result.reasoning.explanation == "saw ['fake_metric']"

    async def test_a_metric_module_receives_an_empty_metrics_dict(self) -> None:
        # Nothing has run yet when METRIC modules run — even a
        # METRIC module registered after another METRIC module sees an
        # empty dict, not a partially-populated one (metrics phase
        # results are only merged in for the REASONING phase).
        class FakeMetricContextReader:
            module_name = "metric_reader"
            module_type = ModuleType.METRIC
            metadata: dict = {}

            async def analyze(self, context) -> ModuleResult:
                return ModuleResult(
                    metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
                    status=ModuleStatus.OK,
                    metric=MetricResult(value=len(context.metrics), unit="count"),
                )

        registry = ModuleRegistry()
        registry.register(FakeMetricModule("first_metric"))
        registry.register(FakeMetricContextReader())

        results = await registry.execute(_transcript())

        reader_result = next(r for r in results if r.metadata.module_name == "metric_reader")
        assert reader_result.metric.value == 0

    async def test_reasoning_context_passthrough_reaches_every_module(self) -> None:
        class FakeReasoningContextReader:
            module_name = "reasoning_context_reader"
            module_type = ModuleType.REASONING
            metadata: dict = {}

            async def analyze(self, context) -> ModuleResult:
                return ModuleResult(
                    metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
                    status=ModuleStatus.OK,
                    reasoning=ReasoningResult(label=context.reasoning_context.get("speaker_role", "unset")),
                )

        # See the comment on test_a_reasoning_module_receives_completed_metric_results
        # above — a REASONING-type fake needs a ReasoningPass configured
        # to run at all under Sprint 4.5.1's registry.
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(FakeReasoningPassLLMReasoner()))
        registry.register(FakeReasoningContextReader())

        results = await registry.execute(_transcript(), reasoning_context={"speaker_role": "presenter"})

        assert results[0].reasoning.label == "presenter"


class TestReasoningPassIntegration:
    """
    Sprint 4.5.1: ModuleRegistry now owns calling ReasoningPass — at
    most once per execute() call, regardless of how many REASONING
    modules are registered — and translating its result (or failure)
    into every registered REASONING module's own ModuleResult.
    """

    async def test_only_one_llm_call_happens_no_matter_how_many_reasoning_modules_are_registered(self) -> None:
        reasoner = FakeReasoningPassLLMReasoner()
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        for module_class in ALL_SIX_REASONING_MODULE_CLASSES:
            registry.register(module_class())

        results = await registry.execute(_transcript())

        assert len(reasoner.calls) == 1
        assert len(results) == 6
        assert all(r.status == ModuleStatus.OK for r in results)

    async def test_each_reasoning_module_gets_its_own_correct_section(self) -> None:
        reasoner = FakeReasoningPassLLMReasoner(
            result=BatchedReasoningResult(
                structure=ReasoningResult(label="structure_label"),
                clarity=ReasoningResult(label="clarity_label"),
                logical_flow=ReasoningResult(label="logical_flow_label"),
                topic_drift=ReasoningResult(label="topic_drift_label"),
                confidence=ReasoningResult(label="confidence_label"),
                conciseness=ReasoningResult(label="conciseness_label"),
            )
        )
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        for module_class in ALL_SIX_REASONING_MODULE_CLASSES:
            registry.register(module_class())

        results = {r.metadata.module_name: r for r in await registry.execute(_transcript())}

        assert results["structure"].reasoning.label == "structure_label"
        assert results["clarity"].reasoning.label == "clarity_label"
        assert results["conciseness"].reasoning.label == "conciseness_label"

    async def test_metric_modules_are_unaffected_by_reasoning_pass_wiring(self) -> None:
        reasoner = FakeReasoningPassLLMReasoner()
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        registry.register(FakeMetricModule("a_metric"))
        registry.register(StructureModule())

        results = {r.metadata.module_name: r for r in await registry.execute(_transcript())}

        assert results["a_metric"].status == ModuleStatus.OK
        assert results["structure"].status == ModuleStatus.OK

    async def test_no_reasoning_pass_configured_fails_every_reasoning_module_without_calling_analyze(self) -> None:
        registry = ModuleRegistry()  # no reasoning_pass
        registry.register(FakeMetricModule("a_metric"))
        registry.register(StructureModule())
        registry.register(ClarityModule())

        results = {r.metadata.module_name: r for r in await registry.execute(_transcript())}

        assert results["a_metric"].status == ModuleStatus.OK
        assert results["structure"].status == ModuleStatus.FAILED
        assert results["structure"].error.reason == AnalysisErrorReason.NO_PROVIDER_CONFIGURED
        assert results["clarity"].status == ModuleStatus.FAILED
        assert results["clarity"].error.reason == AnalysisErrorReason.NO_PROVIDER_CONFIGURED

    async def test_a_failed_batch_call_fails_every_reasoning_module_together(self) -> None:
        reasoner = FakeReasoningPassLLMReasoner(error=LLMTimeoutError("took too long"))
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        registry.register(FakeMetricModule("a_metric"))
        for module_class in ALL_SIX_REASONING_MODULE_CLASSES:
            registry.register(module_class())

        results = {r.metadata.module_name: r for r in await registry.execute(_transcript())}

        # Metric modules are unaffected — an AnalysisReport from a batch
        # failure is never entirely empty (ADR 003 §7).
        assert results["a_metric"].status == ModuleStatus.OK
        # Every reasoning module fails together, with the same
        # translated reason, and the reasoner was only ever called once.
        for module_class in ALL_SIX_REASONING_MODULE_CLASSES:
            name = module_class().module_name
            assert results[name].status == ModuleStatus.FAILED
            assert results[name].error.reason == AnalysisErrorReason.LLM_TIMEOUT
        assert len(reasoner.calls) == 1

    async def test_speaking_pace_metric_reaches_the_batched_prompt_context(self) -> None:
        # Proves the metrics-before-reasoning ordering (Sprint 4.5) still
        # feeds into the *batched* call correctly (Sprint 4.5.1), not
        # just into an individual module's own context as it did before.
        from app.analysis.modules.speaking_pace import SpeakingPaceModule

        reasoner = FakeReasoningPassLLMReasoner()
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        registry.register(SpeakingPaceModule())
        registry.register(ConcisenessModule())

        await registry.execute(_transcript())

        _, template_context = reasoner.calls[0]
        assert template_context["words_per_minute"] != "unknown"

    async def test_no_reasoning_modules_registered_means_no_llm_call_at_all(self) -> None:
        reasoner = FakeReasoningPassLLMReasoner()
        registry = ModuleRegistry(reasoning_pass=ReasoningPass(reasoner))
        registry.register(FakeMetricModule("a_metric"))

        await registry.execute(_transcript())

        assert len(reasoner.calls) == 0


class TestModuleResultValidation:
    def test_ok_metric_result_requires_a_metric_payload(self) -> None:
        with pytest.raises(ValueError):
            ModuleResult(
                metadata=ResultMetadata(module_name="x", module_type=ModuleType.METRIC),
                status=ModuleStatus.OK,
                # metric is missing — should be rejected, not silently accepted.
            )

    def test_failed_result_cannot_also_carry_a_metric_payload(self) -> None:
        from app.analysis.models import ModuleErrorDetail

        with pytest.raises(ValueError):
            ModuleResult(
                metadata=ResultMetadata(module_name="x", module_type=ModuleType.METRIC),
                status=ModuleStatus.FAILED,
                error=ModuleErrorDetail(reason=AnalysisErrorReason.MODULE_ERROR, message="boom"),
                metric=MetricResult(value=1),
            )
