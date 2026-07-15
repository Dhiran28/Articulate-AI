"""
ClarityModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic reasoning
module.

Judges how easy the transcript is to follow for a listener.

Sprint 4.5.1 change: this module no longer calls an LLM itself. It
reads its own `clarity` section out of the `BatchedReasoningResult` that
`ReasoningPass` produced once for all six reasoning dimensions — see
`modules/section_reasoning_base.py` for the shared mechanics, and
`reasoning_pass/batch.py` for where the one actual LLM call happens.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class ClarityModule(_SectionReasoningModule):
    module_name = "clarity"
    section_key = "clarity"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": "Judges how easy the transcript is to follow for a listener.",
            "section_key": self.section_key,
        }
