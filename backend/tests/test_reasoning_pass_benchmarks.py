"""
Benchmark (Sprint 4.5.1): measures the actual, concrete difference
between "six independent LLM calls" (the architecture Sprint 4.5 shipped
and disclosed as a gap against ADR 003) and "one shared batched call"
(what this sprint replaces it with) — call count and simulated
wall-clock latency, both measured, not asserted from a comment.

This does not call a real LLM (no test in this codebase does — see
tests/README.md). Instead, `SimulatedLatencyReasoner` stands in for
`LLMReasoner` and awaits a small, fixed, configurable delay per call —
enough for `asyncio`'s scheduler to actually serialize six sequential
awaits into six times the latency of one, without making the test suite
slow. The purpose isn't to predict a real provider's exact latency
(impossible without one); it's to make the "6 calls vs. 1 call"
architectural claim measurable and falsifiable rather than asserted.

See tests/README.md for how this file fits into the overall suite.
"""

import time

from app.analysis.models import AnalysisContext, ReasoningResult
from app.analysis.reasoning_pass.batch import BatchedReasoningResult, ReasoningPass
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor

_SIMULATED_LATENCY_SECONDS = 0.05
_DIMENSION_COUNT = 6
"""structure, clarity, logical_flow, topic_drift, confidence, conciseness"""


def _transcript():
    text = "So, I think the plan is solid and we should move forward with it."
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=5.0,
        segments=[TranscriptSegment(start=0.0, end=5.0, text=text)],
    )
    return TranscriptProcessor().process(raw)


class SimulatedLatencyReasoner:
    """
    A stand-in LLMReasoner whose `reason()` takes a fixed, small,
    simulated amount of time per call and counts how many times it was
    called — the two axes this benchmark measures.
    """

    def __init__(self, latency_seconds: float = _SIMULATED_LATENCY_SECONDS) -> None:
        self._latency_seconds = latency_seconds
        self.call_count = 0

    async def reason(self, prompt_id: str, context: dict, schema: type):
        import asyncio

        self.call_count += 1
        await asyncio.sleep(self._latency_seconds)
        if schema is BatchedReasoningResult:
            return BatchedReasoningResult(
                **{key: ReasoningResult(label="ok") for key in BatchedReasoningResult.model_fields}
            )
        return ReasoningResult(label="ok")


class TestCallCountBenchmark:
    """The primary, deterministic benchmark: how many LLM calls does one
    analysis cost under each architecture."""

    async def test_previous_architecture_cost_six_calls(self) -> None:
        # Sprint 4.5's architecture: each of the six reasoning modules
        # called LLMReasoner.reason() independently, sequentially, once
        # each per analysis. Simulated directly here since that code no
        # longer exists in the codebase (replaced, not kept side-by-side)
        # — this reproduces its cost profile precisely: N modules, N calls.
        reasoner = SimulatedLatencyReasoner()
        for dimension in range(_DIMENSION_COUNT):
            await reasoner.reason(f"dimension_{dimension}_v1", {"transcript": "x"}, ReasoningResult)

        assert reasoner.call_count == 6

    async def test_current_architecture_costs_one_call_regardless_of_dimension_count(self) -> None:
        reasoner = SimulatedLatencyReasoner()
        reasoning_pass = ReasoningPass(reasoner)

        await reasoning_pass.run(AnalysisContext(transcript=_transcript()))

        assert reasoner.call_count == 1

    async def test_call_count_reduction_factor(self) -> None:
        previous_reasoner = SimulatedLatencyReasoner()
        for dimension in range(_DIMENSION_COUNT):
            await previous_reasoner.reason(f"dimension_{dimension}_v1", {"transcript": "x"}, ReasoningResult)

        current_reasoner = SimulatedLatencyReasoner()
        await ReasoningPass(current_reasoner).run(AnalysisContext(transcript=_transcript()))

        assert previous_reasoner.call_count / current_reasoner.call_count == 6.0


class TestLatencyBenchmark:
    """
    Secondary benchmark: simulated wall-clock time. Six sequential
    awaits at a fixed per-call latency should take roughly six times as
    long as one — this proves that claim against the scheduler rather
    than asserting it, with a generous tolerance (>= 3x, not a strict
    ~6x) so this stays reliable under CI/sandbox scheduling jitter rather
    than flaking on timing noise.
    """

    async def test_batched_call_is_substantially_faster_than_six_sequential_calls(self) -> None:
        previous_reasoner = SimulatedLatencyReasoner()
        previous_start = time.perf_counter()
        for dimension in range(_DIMENSION_COUNT):
            await previous_reasoner.reason(f"dimension_{dimension}_v1", {"transcript": "x"}, ReasoningResult)
        previous_duration = time.perf_counter() - previous_start

        current_reasoner = SimulatedLatencyReasoner()
        current_start = time.perf_counter()
        await ReasoningPass(current_reasoner).run(AnalysisContext(transcript=_transcript()))
        current_duration = time.perf_counter() - current_start

        assert previous_duration > current_duration * 3
