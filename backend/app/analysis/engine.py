from typing import Any

from app.transcript_processing.models import TranscriptProcessingResult

from .errors import AnalysisError, AnalysisErrorReason
from .models import AnalysisReport
from .registry import MODULE_REGISTRY, ModuleRegistry

_MIN_MEANINGFUL_WORD_COUNT = 3
"""Below this many words there's nothing meaningful to evaluate — the
engine short-circuits once, up front, with TRANSCRIPT_EMPTY instead of
letting every module independently discover there's no content and
return a report full of confusing near-empty results (ADR 003 §4).
Deliberately low and adjustable: this guards against literally-empty or
near-empty input, not against short-but-real utterances."""


class AnalysisEngine:
    """
    The Communication Intelligence Engine's runner (ADR 003 §1): accepts
    a transcript, executes every registered module via ModuleRegistry,
    and returns one structured AnalysisReport.

    Deliberately thin. `ModuleRegistry.execute()` (registry.py) owns
    running modules and isolating their failures; this class owns the
    one thing that has to happen before any module runs (the empty-
    transcript guard) and shaping the final report. Splitting it this
    way means the registry can be tested and reused (e.g. by something
    that wants "just run these modules" without the guard/report
    wrapping) independently of the engine.
    """

    def __init__(self, registry: ModuleRegistry | None = None) -> None:
        # Defaults to the shared MODULE_REGISTRY, but accepts an
        # injected one — what makes this class testable against a
        # fresh, isolated registry instead of the shared global.
        self._registry = MODULE_REGISTRY if registry is None else registry

    async def run(
        self,
        transcript_id: str,
        transcript: TranscriptProcessingResult,
        reasoning_context: dict[str, Any] | None = None,
    ) -> AnalysisReport:
        """
        Sprint 4.5 adds the optional `reasoning_context` passthrough — an
        open extensibility hook (see AnalysisContext in models.py) handed
        unchanged to every module via the registry's two-phase execution.
        Unused by any module built so far; it exists so a future caller
        doesn't require another breaking signature change to supply it.
        """
        self._guard_non_empty(transcript)

        report = AnalysisReport(transcript_id=transcript_id)
        for result in await self._registry.execute(transcript, reasoning_context=reasoning_context):
            report.modules[result.metadata.module_name] = result

        return report

    def _guard_non_empty(self, transcript: TranscriptProcessingResult) -> None:
        word_count = len(transcript.processed_transcript.text.split())
        if word_count < _MIN_MEANINGFUL_WORD_COUNT:
            raise AnalysisError(
                AnalysisErrorReason.TRANSCRIPT_EMPTY,
                "There isn't enough transcript content to analyze.",
            )
