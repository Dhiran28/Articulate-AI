"""
ConfidenceModule (Sprint 4.5, rewritten Sprint 4.5.1) — semantic
reasoning module.

Judges how confidently the speaker comes across.

Sprint 4.5.1 change: this module no longer calls an LLM itself, and no
longer computes its own hedge-word sub-signal either — both moved into
`ReasoningPass`/`signals.py` (`compute_hedge_signal`), since the hedge
count now feeds one combined prompt, not a per-module one. This module
now does exactly what every other section-reading module does: reads
its own `confidence` section out of the `BatchedReasoningResult` that
`ReasoningPass` produced once for all six reasoning dimensions — see
`modules/section_reasoning_base.py` for the shared mechanics.
"""

from typing import Any

from .section_reasoning_base import _SectionReasoningModule


class ConfidenceModule(_SectionReasoningModule):
    module_name = "confidence"
    section_key = "confidence"

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.2.0",
            "description": (
                "Judges how confidently the speaker comes across. The deterministic "
                "hedge-word signal that used to be computed here now lives in "
                "reasoning_pass/signals.py, feeding the one combined prompt instead."
            ),
            "section_key": self.section_key,
        }
