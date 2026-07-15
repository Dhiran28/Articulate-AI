"""
Deterministic sub-signals fed into the one combined reasoning prompt
(Sprint 4.5.1).

Both functions here used to live inside individual reasoning modules
(`ConfidenceModule` computed its own hedge-word count; `ConcisenessModule`
read `context.metrics["speaking_pace"]` itself) back when each module
built its own LLM call. Now that `ReasoningPass` (batch.py) is the only
thing that builds a prompt, these are computed exactly once, here, and
folded into the one combined template context — the direct fix for
Sprint 4.5's "no duplicated ... parsing" concern applied to input
preparation as well as output handling: six modules independently
recomputing (or worse, six copies of) the same regex or dict lookup
would be exactly the duplication this sprint exists to remove.

Pure functions, no I/O, no LLM calls — same determinism guarantee
Sprint 4.3's Metric modules hold themselves to, because this is the
same kind of computation, just relocated.
"""

import re

from ..models import ModuleResult, ModuleStatus

# Deliberately small and conservative — see the original ConfidenceModule
# docstring (Sprint 4.5) for why: false positives are worse here than a
# few missed hedges, since this signal exists to sharpen the combined
# prompt's reasoning, not to substitute for it.
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

_HEDGE_PATTERN = re.compile(r"\b(" + "|".join(re.escape(p) for p in _DEFAULT_HEDGE_PHRASES) + r")\b", re.IGNORECASE)


def compute_hedge_signal(transcript_text: str, *, example_limit: int = 5) -> tuple[int, str]:
    """
    Returns `(hedge_word_count, hedge_word_examples)` — a count of
    hedging phrases found in `transcript_text`, and a short,
    comma-joined, deduplicated sample of which ones (capped at
    `example_limit`, `"none found"` if there are none). Feeds
    `ConfidenceModule`'s section of the combined prompt, giving the model
    concrete textual evidence to reason over rather than asking it to
    both find and judge the hedging in one step.
    """
    matches = _HEDGE_PATTERN.findall(transcript_text)
    examples = sorted({m.lower() for m in matches})[:example_limit]
    return len(matches), (", ".join(examples) if examples else "none found")


def extract_speaking_pace_hints(metrics: dict[str, ModuleResult]) -> tuple[str, str]:
    """
    Returns `(words_per_minute, average_sentence_length)` as strings
    (template variables are always strings — see `PromptTemplate.render`)
    read from `metrics["speaking_pace"]` (Sprint 4.3's `SpeakingPaceModule`
    output) when present and successful, or `("unknown", "unknown")`
    otherwise. Feeds `ConcisenessModule`'s section of the combined
    prompt. Read-only and best-effort by design: this never calls
    `SpeakingPaceModule` itself, only reads whatever `ModuleRegistry`'s
    metric phase already put in `context.metrics` (see registry.py) —
    the same isolation guarantee the original per-module version of this
    logic had.
    """
    pace_result = metrics.get("speaking_pace")
    if pace_result is None or pace_result.status is not ModuleStatus.OK or pace_result.metric is None:
        return "unknown", "unknown"

    words_per_minute = pace_result.metric.value
    average_sentence_length = pace_result.metric.details.get("average_sentence_length")

    return (
        str(words_per_minute) if words_per_minute is not None else "unknown",
        str(average_sentence_length) if average_sentence_length is not None else "unknown",
    )
