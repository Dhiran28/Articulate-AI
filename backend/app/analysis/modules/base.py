from typing import Protocol, runtime_checkable

from app.transcript_processing.models import TranscriptProcessingResult

from ..models import ModuleCategory, ModuleResult


@runtime_checkable
class AnalysisModule(Protocol):
    """
    Per ADR 003 §1: "a thing that takes a TranscriptProcessingResult and
    returns a ModuleResult." Used directly by:

      - Metric modules (Filler Words, Hesitations, Repetitions, Speaking
        Pace) — pure computation, no LLM call.
      - Any future "deep analysis" module that needs its own independent
        LLM call rather than sharing the batched reasoning request (see
        BatchedReasoningModule in batched.py, and ADR 003 §1's "deep
        analysis escape hatch").

    `@runtime_checkable` is what lets AnalysisEngine tell an
    AnalysisModule apart from a BatchedReasoningModule with a plain
    isinstance() check, since MODULE_REGISTRY holds both shapes mixed
    together (see registry.py) — the standard way to do exactly this
    with typing.Protocol.

    No implementations exist yet. Sprint 4.2 builds only the contract
    every future module plugs into — see registry.py and this package's
    module docstring for what's deliberately deferred.
    """

    name: str
    category: ModuleCategory

    async def analyze(self, transcript: TranscriptProcessingResult) -> ModuleResult: ...
