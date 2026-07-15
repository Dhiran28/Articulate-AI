"""
ClarityModule (Sprint 4.5) — semantic reasoning module.

Judges how easy the transcript is to follow for a listener: whether
ideas are expressed plainly, whether jargon or ambiguous phrasing
obscures the point. Like StructureModule, this is a judgment call no
deterministic heuristic can honestly make, so it's a reasoning module
that needs only the transcript text.
"""

from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext
from .reasoning_base import _BaseReasoningModule


class ClarityModule(_BaseReasoningModule):
    module_name = "clarity"
    prompt_id = "clarity_v1"

    def __init__(self, reasoner: LLMReasoner) -> None:
        super().__init__(reasoner)
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Judges how easy the transcript is to follow for a listener.",
            "prompt_id": self.prompt_id,
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        return {"transcript": context.transcript.processed_transcript.text}
