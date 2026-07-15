"""
ConcisenessModule (Sprint 4.5) — semantic reasoning module.

Judges whether the speaker says what they mean efficiently, or pads it
out with unnecessary words. Unlike the other five reasoning modules,
this one deliberately reads `context.metrics` — Sprint 4.5's whole reason
for widening AnalysisModule to AnalysisContext in the first place (see
models.py's AnalysisContext docstring): if SpeakingPaceModule (Sprint
4.3) already ran and computed `average_sentence_length`, that's a
concrete, deterministic signal worth handing the LLM alongside the raw
transcript, instead of asking the model to eyeball sentence length
itself from unstructured text.

This is read-only and best-effort: `context.metrics` only contains
`speaking_pace` if that Metric module was registered and ran
successfully (ModuleRegistry's two-phase execution puts every Metric
result there before any Reasoning module runs — see registry.py). If
it's missing or failed, this module still runs, just without that extra
hint — it never calls SpeakingPaceModule itself (ADR 003 §7's per-module
isolation would be pointless if a Reasoning module could reach into
another module directly instead of through the registry-populated
context).
"""

from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext, ModuleStatus
from .reasoning_base import _BaseReasoningModule


class ConcisenessModule(_BaseReasoningModule):
    module_name = "conciseness"
    prompt_id = "conciseness_v1"

    def __init__(self, reasoner: LLMReasoner) -> None:
        super().__init__(reasoner)
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": (
                "Judges whether the speaker communicates efficiently, using "
                "speaking_pace's metrics as supporting context when available."
            ),
            "prompt_id": self.prompt_id,
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        words_per_minute, average_sentence_length = self._speaking_pace_hints(context)

        return {
            "transcript": context.transcript.processed_transcript.text,
            "words_per_minute": words_per_minute,
            "average_sentence_length": average_sentence_length,
        }

    def _speaking_pace_hints(self, context: AnalysisContext) -> tuple[str, str]:
        pace_result = context.metrics.get("speaking_pace")
        if pace_result is None or pace_result.status is not ModuleStatus.OK or pace_result.metric is None:
            return "unknown", "unknown"

        words_per_minute = pace_result.metric.value
        average_sentence_length = pace_result.metric.details.get("average_sentence_length")

        return (
            str(words_per_minute) if words_per_minute is not None else "unknown",
            str(average_sentence_length) if average_sentence_length is not None else "unknown",
        )
