"""
StructureModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic
reasoning module.

Judges whether the transcript has a recognizable structural shape (an
opening framing, a body, a close — or whatever shape the combined
prompt asks the model to look for). This is exactly the "structural
thinking" dimension ADR 003 named as the CIE's founding motivation.

Sprint 4.5.1 change: this module no longer calls an LLM itself. It
reads its own `structure` section out of the `BatchedReasoningResult`
that `ReasoningPass` produced once for all six reasoning dimensions —
see `modules/section_reasoning_base.py` for the shared mechanics, and
`reasoning_pass/batch.py` for where the one actual LLM call happens.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class StructureModule(_SectionReasoningModule):
    module_name = "structure"
    section_key = "structure"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": "Judges whether the transcript has a recognizable structural shape.",
            "section_key": self.section_key,
        }
