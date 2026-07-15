"""
TopicDriftModule (Sprint 4.5) — semantic reasoning module.

Judges whether the transcript stays on its apparent topic or wanders.
"Drift" is a semantic judgment about subject matter, not something a
keyword count or n-gram check can honestly measure (two completely
different phrasings can be perfectly on-topic; two similar-looking
phrasings can be unrelated) — hence a reasoning module. Needs only the
transcript text.
"""

from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext
from .reasoning_base import _BaseReasoningModule


class TopicDriftModule(_BaseReasoningModule):
    module_name = "topic_drift"
    prompt_id = "topic_drift_v1"

    def __init__(self, reasoner: LLMReasoner) -> None:
        super().__init__(reasoner)
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Judges whether the transcript stays on topic or drifts.",
            "prompt_id": self.prompt_id,
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        return {"transcript": context.transcript.processed_transcript.text}
