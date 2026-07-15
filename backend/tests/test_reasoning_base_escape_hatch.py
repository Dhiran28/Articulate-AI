"""
A minimal test proving ADR 003 §1's "deep analysis" escape hatch is
still real, working infrastructure after Sprint 4.5.1 — not just
documentation. `_BaseReasoningModule` (app/analysis/modules/
reasoning_base.py) is unused by any of the six current concrete
reasoning modules (they all moved to `_SectionReasoningModule` /
ReasoningPass's batched design instead), but a future module that
genuinely needs its own independent LLM call can still subclass it.

See tests/README.md for how this file fits into the overall suite.
"""

from typing import Any

from app.analysis.errors import AnalysisErrorReason
from app.analysis.models import AnalysisContext, ModuleStatus, ModuleType, ReasoningResult
from app.analysis.modules.base import AnalysisModule
from app.analysis.modules.reasoning_base import _BaseReasoningModule
from app.llm.errors import LLMTimeoutError
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor


def _transcript(text: str = "Hello there, this is a test transcript."):
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=2.0,
        segments=[TranscriptSegment(start=0.0, end=2.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


class _StandaloneDeepAnalysisModule(_BaseReasoningModule):
    """A stand-in for a hypothetical future module that opts out of the
    shared batched pass and makes its own independent LLMReasoner call —
    exactly the shape ADR 003 §1 reserves this escape hatch for."""

    module_name = "deep_analysis_example"
    prompt_id = "deep_analysis_v1"
    metadata: dict[str, Any] = {"version": "0.0.1-test"}

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        return {"transcript": context.transcript.processed_transcript.text}


class FakeLLMReasoner:
    def __init__(self, result: ReasoningResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def reason(self, prompt_id: str, context: dict, schema: type) -> ReasoningResult:
        self.calls.append((prompt_id, context))
        if self._error is not None:
            raise self._error
        return self._result if self._result is not None else ReasoningResult(label="ok")


class TestDeepAnalysisEscapeHatch:
    def test_satisfies_the_same_analysis_module_protocol(self) -> None:
        module = _StandaloneDeepAnalysisModule(FakeLLMReasoner())
        assert isinstance(module, AnalysisModule)
        assert module.module_type == ModuleType.REASONING

    async def test_makes_its_own_independent_llm_call(self) -> None:
        reasoner = FakeLLMReasoner(result=ReasoningResult(label="deep_result"))
        module = _StandaloneDeepAnalysisModule(reasoner)

        result = await module.analyze(AnalysisContext(transcript=_transcript()))

        assert len(reasoner.calls) == 1
        assert reasoner.calls[0][0] == "deep_analysis_v1"
        assert result.status == ModuleStatus.OK
        assert result.reasoning.label == "deep_result"

    async def test_llm_errors_still_map_to_a_failed_module_result(self) -> None:
        reasoner = FakeLLMReasoner(error=LLMTimeoutError("too slow"))
        module = _StandaloneDeepAnalysisModule(reasoner)

        result = await module.analyze(AnalysisContext(transcript=_transcript()))

        assert result.status == ModuleStatus.FAILED
        assert result.error.reason == AnalysisErrorReason.LLM_TIMEOUT
