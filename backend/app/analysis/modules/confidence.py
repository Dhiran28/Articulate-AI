"""
ConfidenceModule (Sprint 4.5) — semantic reasoning module.

Judges how confidently the speaker comes across. Confidence is
ultimately a semantic read (tone, word choice, framing), so the actual
judgment still flows through the shared LLMReasoner like every other
reasoning module here — but this module is deliberately given one small
deterministic assist no other reasoning module has: a local, regex-based
count of hedging language ("I think," "sort of," "maybe," "kind of," ...)
computed here, in Python, with no LLM call. That count and a handful of
example hedges are handed to the prompt as extra context, giving the
model concrete textual evidence to reason over rather than asking it to
both find and judge the hedging in one step.

This sub-signal is deliberately *not* a separate output field — it never
appears anywhere in the returned ModuleResult; it exists purely to
enrich the LLM prompt's `$hedge_signal` variable. The module still
returns nothing but a ReasoningResult, same as the other five, keeping
"no scores" intact: the hedge count is a hint fed into the model's
reasoning, not a metric this module reports on its own authority.
"""

import re
from typing import Any

from app.llm.reasoner import LLMReasoner

from ..models import AnalysisContext
from .reasoning_base import _BaseReasoningModule

# Deliberately small and conservative — false positives (flagging a
# confident, precise use of "I think" as hedging) are worse for this
# module's purpose than a few missed hedges, since this signal is meant
# to sharpen the LLM's reasoning, not substitute for it.
_DEFAULT_HEDGE_PHRASES = (
    "i think",
    "i guess",
    "i suppose",
    "sort of",
    "kind of",
    "maybe",
    "probably",
    "i'm not sure",
    "not sure",
    "might be",
    "could be",
    "i feel like",
)


class ConfidenceModule(_BaseReasoningModule):
    module_name = "confidence"
    prompt_id = "confidence_v1"

    def __init__(self, reasoner: LLMReasoner, hedge_phrases: tuple[str, ...] = _DEFAULT_HEDGE_PHRASES) -> None:
        super().__init__(reasoner)
        self._hedge_phrases = hedge_phrases
        self._hedge_pattern = re.compile(
            r"\b(" + "|".join(re.escape(p) for p in hedge_phrases) + r")\b", re.IGNORECASE
        )
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": (
                "Judges how confidently the speaker comes across, assisted by a "
                "deterministic local hedge-word count fed into the prompt as context."
            ),
            "prompt_id": self.prompt_id,
            "hedge_phrase_count": len(hedge_phrases),
        }

    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        text = context.transcript.processed_transcript.text
        matches = self._hedge_pattern.findall(text)

        hedge_count = len(matches)
        # A short, deduplicated sample rather than every match — enough
        # for the model to see concrete examples without bloating the
        # prompt with a long, repetitive list on a hedge-heavy transcript.
        example_hedges = sorted({m.lower() for m in matches})[:5]

        return {
            "transcript": text,
            "hedge_word_count": str(hedge_count),
            "hedge_word_examples": ", ".join(example_hedges) if example_hedges else "none found",
        }
