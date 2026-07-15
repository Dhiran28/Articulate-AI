"""
ConcisenessModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic
reasoning module.

Judges whether the speaker says what they mean efficiently, or pads it
out with unnecessary words.

Sprint 4.5.1 change: this module no longer calls an LLM itself, and no
longer reads `context.metrics["speaking_pace"]` itself either — that
extraction moved into `ReasoningPass`/`signals.py`
(`extract_speaking_pace_hints`), since it now feeds one combined prompt,
not a per-module one. This module now does exactly what every other
section-reading module does: reads its own `conciseness` section out of
the `BatchedReasoningResult` that `ReasoningPass` produced once for all
six reasoning dimensions — see `modules/section_reasoning_base.py` for
the shared mechanics.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class ConcisenessModule(_SectionReasoningModule):
    module_name = "conciseness"
    section_key = "conciseness"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": (
                "Judges whether the speaker communicates efficiently. The "
                "speaking_pace metric hint that used to be read here now lives in "
                "reasoning_pass/signals.py, feeding the one combined prompt instead."
            ),
            "section_key": self.section_key,
        }
