"""
LogicalFlowModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic
reasoning module.

Judges whether consecutive ideas in the transcript connect logically.

Sprint 4.5.1 change: this module no longer calls an LLM itself. It
reads its own `logical_flow` section out of the `BatchedReasoningResult`
that `ReasoningPass` produced once for all six reasoning dimensions —
see `modules/section_reasoning_base.py` for the shared mechanics, and
`reasoning_pass/batch.py` for where the one actual LLM call happens.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class LogicalFlowModule(_SectionReasoningModule):
    module_name = "logical_flow"
    section_key = "logical_flow"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": "Judges whether consecutive ideas in the transcript connect logically.",
            "section_key": self.section_key,
        }
