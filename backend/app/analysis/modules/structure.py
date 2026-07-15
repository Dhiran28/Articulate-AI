"""
StructureModule (Sprint 4.5) — semantic reasoning module.

Judges whether the transcript has a recognizable structural shape (an
opening framing, a body, a close — or whatever shape the prompt asks the
model to look for). This is exactly the "structural thinking" dimension
ADR 003 named as the CIE's founding motivation and Sprint 4.1 explicitly
scoped as semantic, not deterministic — no regex or heuristic can judge
"does this have a coherent structure," which is why this module exists
as a reasoning module rather than a metric module.

Needs only the transcript text — no deterministic metric or
reasoning_context input changes what "does this have structure" means,
so `_build_template_context` is the simplest of the six.
"""

from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext
from .reasoning_base import _BaseReasoningModule


class StructureModule(_BaseReasoningModule):
    module_name = "structure"
    prompt_id = "structure_v1"

    def __init__(self, reasoner: LLMReasoner) -> None:
        super().__init__(reasoner)
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Judges whether the transcript has a recognizable structural shape.",
            "prompt_id": self.prompt_id,
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        return {"transcript": context.transcript.processed_transcript.text}
