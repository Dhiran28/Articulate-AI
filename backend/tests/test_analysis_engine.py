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
from app.analysis.registry import DuplicateModuleError, ModuleRegistry
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor


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

    async def analyze(self, transcript) -> ModuleResult:
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

    async def analyze(self, transcript) -> ModuleResult:
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

    async def analyze(self, transcript) -> ModuleResult:
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
    async def test_modules_execute_in_registration_order(self) -> None:
        registry = ModuleRegistry()
        registry.register(FakeMetricModule("first"))
        registry.register(FakeReasoningModule("second"))
        registry.register(FakeMetricModule("third"))

        results = await registry.execute(_transcript())

        assert [r.metadata.module_name for r in results] == ["first", "second", "third"]

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
        registry = ModuleRegistry()
        registry.register(FakeMetricModule("healthy_one"))
        registry.register(FakeCrashingModule("crasher"))
        registry.register(FakeReasoningModule("healthy_two"))
        engine = AnalysisEngine(registry=registry)

        report = await engine.run("t-1", _transcript())

        assert report.modules["healthy_one"].status == ModuleStatus.OK
        assert report.modules["healthy_two"].status == ModuleStatus.OK
        assert report.modules["crasher"].status == ModuleStatus.FAILED
        assert report.modules["crasher"].error.reason == AnalysisErrorReason.MODULE_ERROR


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
