import logging

from app.transcript_processing.models import TranscriptProcessingResult

from .errors import AnalysisError, AnalysisErrorReason
from .models import AnalysisReport, ModuleResult, ModuleStatus
from .modules.base import AnalysisModule
from .modules.batched import BatchedReasoningModule
from .registry import MODULE_REGISTRY, RegisteredModule

logger = logging.getLogger(__name__)

_MIN_MEANINGFUL_WORD_COUNT = 3
"""Below this many words there's nothing meaningful to evaluate across
ten dimensions — the engine short-circuits once, up front, with
TRANSCRIPT_EMPTY instead of letting every module independently discover
there's no content and return ten confusing near-empty results (ADR 003
§4). Deliberately low and adjustable: this guards against literally-empty
or near-empty input, not against short-but-real utterances."""


class AnalysisEngine:
    """
    Orchestrates the Communication Intelligence Engine (ADR 003 §1).

    Runs every module in the registry independently — no module ever
    sees another module's output — and assembles their results into one
    AnalysisReport. A module's failure never affects any other module's
    result or the rest of the report (ADR 003 §7): every module call is
    isolated, and a module that raises is represented as a `failed`
    ModuleResult, never an exception that propagates out of analyze().

    Sprint 4.2 builds this orchestration shape only. MODULE_REGISTRY is
    empty — no real module exists yet (see registry.py) — and there is
    no real ReasoningPass yet either. Any BatchedReasoningModule the
    registry ever contains before that seam is built fails with
    REASONING_PASS_UNAVAILABLE rather than being silently skipped or
    fabricating a result: an incomplete pipeline should say so, the same
    principle Sprint 3.5 applied to false-start detection rather than
    faking a count it couldn't honestly produce.
    """

    def __init__(self, modules: list[RegisteredModule] | None = None) -> None:
        # Accepting an explicit module list — defaulting to the shared
        # MODULE_REGISTRY, but overridable — is what makes this class
        # testable in isolation with fake modules, rather than always
        # reaching for a module-level global. Same reasoning that keeps
        # AudioService constructed with injected dependencies.
        self._modules = MODULE_REGISTRY if modules is None else modules

    async def analyze(self, transcript_id: str, transcript: TranscriptProcessingResult) -> AnalysisReport:
        self._guard_non_empty(transcript)

        report = AnalysisReport(transcript_id=transcript_id)

        for module in self._modules:
            result = await self._run_module(module, transcript)
            report.modules[result.module_name] = result

        return report

    def _guard_non_empty(self, transcript: TranscriptProcessingResult) -> None:
        word_count = len(transcript.processed_transcript.text.split())
        if word_count < _MIN_MEANINGFUL_WORD_COUNT:
            raise AnalysisError(
                AnalysisErrorReason.TRANSCRIPT_EMPTY,
                "There isn't enough transcript content to analyze.",
            )

    async def _run_module(self, module: RegisteredModule, transcript: TranscriptProcessingResult) -> ModuleResult:
        name = getattr(module, "name", module.__class__.__name__)
        category = getattr(module, "category", None)

        try:
            if isinstance(module, BatchedReasoningModule):
                # No ReasoningPass exists yet — see this class's
                # docstring and ADR 003 §6, where building the app/llm/
                # seam + ReasoningPass is named as its own future sprint.
                # A module reaching this branch is registered correctly;
                # the engine just has nothing yet to run it through.
                return ModuleResult(
                    module_name=name,
                    category=category,
                    status=ModuleStatus.FAILED,
                    reason=AnalysisErrorReason.REASONING_PASS_UNAVAILABLE,
                    message="Batched reasoning isn't wired up yet.",
                )

            if isinstance(module, AnalysisModule):
                return await module.analyze(transcript)

            # A registry entry satisfying neither Protocol is a wiring
            # bug (someone appended something to MODULE_REGISTRY that
            # doesn't implement either contract), not a runtime failure
            # of the module itself — surfaced the same way any other
            # unexpected failure is, below, rather than a separate silent
            # branch.
            raise TypeError(f"{name!r} implements neither AnalysisModule nor BatchedReasoningModule")

        except Exception:
            # Deliberately broad: a module crashing must never take down
            # the rest of the report (ADR 003 §7). The specific exception
            # is logged for debugging; the caller only ever sees a
            # classified failure — MODULE_ERROR signals specifically that
            # the *engine* caught this, not that the module diagnosed and
            # reported its own failure the way a well-behaved module
            # normally would (see AnalysisErrorReason.MODULE_ERROR).
            logger.exception("Analysis module %s raised during analyze()", name)
            return ModuleResult(
                module_name=name,
                category=category,
                status=ModuleStatus.FAILED,
                reason=AnalysisErrorReason.MODULE_ERROR,
                message="This module failed unexpectedly and could not complete.",
            )
