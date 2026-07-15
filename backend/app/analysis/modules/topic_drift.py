"""
TopicDriftModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic
reasoning module.

Judges whether the transcript stays on its apparent topic or wanders.

Sprint 4.5.1 change: this module no longer calls an LLM itself. It
reads its own `topic_drift` section out of the `BatchedReasoningResult`
that `ReasoningPass` produced once for all six reasoning dimensions —
see `modules/section_reasoning_base.py` for the shared mechanics, and
`reasoning_pass/batch.py` for where the one actual LLM call happens.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class TopicDriftModule(_SectionReasoningModule):
    module_name = "topic_drift"
    section_key = "topic_drift"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": "Judges whether the transcript stays on topic or drifts.",
            "section_key": self.section_key,
        }
