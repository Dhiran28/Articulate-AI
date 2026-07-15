"""
LogicalFlowModule (Sprint 4.5) — semantic reasoning module.

Judges whether one idea leads to the next in a way that makes logical
sense — distinct from StructureModule (does the transcript have a
recognizable shape at all) by focusing on the connective tissue between
consecutive points rather than the overall shape. Needs only the
transcript text.
"""

from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext
from .reasoning_base import _BaseReasoningModule


class LogicalFlowModule(_BaseReasoningModule):
    module_name = "logical_flow"
    prompt_id = "logical_flow_v1"

    def __init__(self, reasoner: LLMReasoner) -> None:
        super().__init__(reasoner)
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Judges whether consecutive ideas in the transcript connect logically.",
            "prompt_id": self.prompt_id,
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        return {"transcript": context.transcript.processed_transcript.text}
