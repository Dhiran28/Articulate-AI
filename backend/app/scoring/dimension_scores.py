"""
Per-module scoring functions (Milestone 5) — turn one module's
ModuleResult into a bounded 0-100 sub-score plus a short, human-readable
`driver` string explaining what produced it. `engine.py` calls exactly
one of these per module, based on `module_name`, and combines the
results using weights.py's documented weights.

Every threshold/band here is a plain, round, documented heuristic —
not empirically fit to any dataset (none exists yet for this product;
see weights.py's module docstring for the same disclosure applied to
the cross-module weights). Each function's docstring states its
reasoning so the "transparent" half of "transparent weighted scoring
algorithm" holds at the level of individual formulas, not just the
top-level weights.
"""

from app.analysis.models import ModuleResult, ModuleStatus

# ---------------------------------------------------------------------------
# Metric modules (Sprint 4.3) — deterministic inputs, deterministic scores.
# ---------------------------------------------------------------------------

FILLER_RATE_CEILING_PER_100_WORDS = 10.0
"""
FillerWordModule.details["frequency_per_100_words"] at or above this
scores 0; a rate of 0 scores 100; linear in between. Chosen as a clean,
round ceiling — "1 filler word in every 10 spoken" — deliberately high
enough that only a genuinely filler-heavy transcript bottoms out,
disclosed as a heuristic choice, not a cited threshold from speech
research this project doesn't have access to validate.
"""


def score_filler_words(result: ModuleResult) -> tuple[float, str]:
    frequency = result.metric.details.get("frequency_per_100_words", 0.0)
    score = 100.0 * _clamp(1.0 - (frequency / FILLER_RATE_CEILING_PER_100_WORDS), 0.0, 1.0)
    return round(score, 1), f"{frequency} filler words per 100 words spoken"


def score_hesitations(result: ModuleResult) -> tuple[float, str]:
    """
    Scores the *proportion* of a speaker's own pauses that were long
    (HesitationModule's `long_pause_threshold_seconds`-based
    classification), not a raw count against an invented ceiling — a
    speaker who pauses often but briefly is doing something very
    different from one whose pauses are frequently long, and this
    formula only penalizes the latter. A transcript with zero detected
    pauses scores 100 (nothing to penalize), not undefined.
    """
    pause_count = result.metric.value or 0
    long_pauses = result.metric.details.get("long_pauses", [])

    if not pause_count:
        return 100.0, "no pauses detected"

    long_pause_ratio = len(long_pauses) / pause_count
    score = 100.0 * (1.0 - long_pause_ratio)
    return round(score, 1), f"{len(long_pauses)} of {pause_count} pauses were long"


REPETITION_COUNT_CEILING = 8
"""
RepetitionModule.metric.value (its headline repetition_count) at or
above this scores 0; 0 repetitions scores 100; linear in between. An
absolute count, not normalized per-100-words like FillerWordModule's
rate — RepetitionModule's own output doesn't carry a word-count
denominator (see app/analysis/README.md), so this is a disclosed
simplification: a very long transcript with the same absolute
repetition count as a short one is treated identically here, which a
future revision could improve by adding length normalization to
RepetitionModule itself.
"""


def score_repetitions(result: ModuleResult) -> tuple[float, str]:
    count = result.metric.value or 0
    score = 100.0 * _clamp(1.0 - (count / REPETITION_COUNT_CEILING), 0.0, 1.0)
    return round(score, 1), f"{count} repetitions detected"


PACE_FLOOR_WPM = 80.0
PACE_IDEAL_LOW_WPM = 120.0
PACE_IDEAL_HIGH_WPM = 160.0
PACE_CEILING_WPM = 200.0
"""
SpeakingPaceModule.metric.value (words per minute) scores 100 anywhere
in [120, 160] — a commonly cited comfortable conversational/presentation
pace range, disclosed here as a widely-referenced rule of thumb rather
than a citation to a specific controlled study this project has
verified. Below 120, score falls linearly to 0 at 80 wpm (a pace slow
enough to risk losing a listener's attention); above 160, score falls
linearly to 0 at 200 wpm (fast enough to risk losing comprehensibility).
The two slopes are symmetric in shape (40 wpm of falloff on each side)
even though the underlying human experience of "too slow" and "too
fast" isn't necessarily symmetric — chosen for simplicity and
documented as such, not derived from asymmetric data this project
doesn't have.
"""


def score_speaking_pace(result: ModuleResult) -> tuple[float, str]:
    wpm = result.metric.value or 0.0

    if PACE_IDEAL_LOW_WPM <= wpm <= PACE_IDEAL_HIGH_WPM:
        score = 100.0
    elif wpm < PACE_IDEAL_LOW_WPM:
        score = 100.0 * _clamp((wpm - PACE_FLOOR_WPM) / (PACE_IDEAL_LOW_WPM - PACE_FLOOR_WPM), 0.0, 1.0)
    else:
        score = 100.0 * _clamp((PACE_CEILING_WPM - wpm) / (PACE_CEILING_WPM - PACE_IDEAL_HIGH_WPM), 0.0, 1.0)

    return round(score, 1), f"{wpm} words per minute"


# ---------------------------------------------------------------------------
# Reasoning modules (Sprint 4.5/4.5.1) — three-tier label bands.
# ---------------------------------------------------------------------------

REASONING_LABEL_BANDS: dict[str, dict[str, float]] = {
    # Every dimension's three allowed labels (see
    # reasoning_pass/prompts/analysis/reasoning_pass_v1.md, which
    # constrains the model to emit exactly one of these per dimension)
    # map to the same three anchor scores: 100 (fully meets the
    # standard), 60 (partially meets it), 20 (does not meet it). A
    # symmetric three-tier band, not five or ten, because ReasoningResult
    # (app/analysis/models.py) deliberately carries no numeric score
    # field at all — see ADR 003's "no scores" requirement — so this is
    # the finest-grained distinction available without asking the model
    # for a number, which this project has explicitly chosen not to do
    # (a free-form numeric score from an LLM is exactly the kind of
    # unverifiable precision ADR 003 §5/§7 warns against elsewhere).
    "structure": {"clear_structure": 100.0, "partial_structure": 60.0, "no_structure": 20.0},
    "clarity": {"clear": 100.0, "somewhat_unclear": 60.0, "unclear": 20.0},
    "logical_flow": {"coherent_flow": 100.0, "minor_disconnects": 60.0, "disjointed": 20.0},
    "topic_drift": {"on_topic": 100.0, "minor_drift": 60.0, "significant_drift": 20.0},
    "confidence": {"confident": 100.0, "somewhat_hesitant": 60.0, "uncertain": 20.0},
    "conciseness": {"concise": 100.0, "somewhat_padded": 60.0, "verbose": 20.0},
}

FALLBACK_UNKNOWN_LABEL_SCORE = 60.0
"""
If a reasoning module's label doesn't match its documented vocabulary
(the model deviated from the prompt's instructions despite the
constraint — see reasoning_pass_v1.md), this dimension is scored at the
middle anchor (60, "partially meets the standard") rather than 0, 100,
or raising. Treated as a soft, disclosed interpretation — not the "never
silently repair" discipline app/llm applies to malformed JSON/schema
failures, which are hard parse failures with no reasonable middle
ground. A label the model phrased slightly differently than expected is
a much softer failure mode, and defaulting to neutral is the least
presumptuous score to assign without discarding the dimension entirely.
"""


def score_reasoning_dimension(module_name: str, result: ModuleResult) -> tuple[float, str]:
    label = result.reasoning.label
    bands = REASONING_LABEL_BANDS[module_name]

    if label in bands:
        return bands[label], label

    return FALLBACK_UNKNOWN_LABEL_SCORE, f"{label!r} (unrecognized label — neutral fallback applied)"


# ---------------------------------------------------------------------------

_METRIC_SCORERS = {
    "filler_words": score_filler_words,
    "hesitations": score_hesitations,
    "repetitions": score_repetitions,
    "speaking_pace": score_speaking_pace,
}


def score_module(module_name: str, result: ModuleResult) -> tuple[float, str]:
    """
    Dispatches to the right scoring function for `module_name`. Only
    ever called on a `ModuleResult` with `status == ModuleStatus.OK`
    (see engine.py) — a failed module is never scored, its weight is
    redistributed instead.
    """
    if result.status is not ModuleStatus.OK:
        raise ValueError(f"score_module called on a non-OK ModuleResult for {module_name!r}.")

    if module_name in _METRIC_SCORERS:
        return _METRIC_SCORERS[module_name](result)

    if module_name in REASONING_LABEL_BANDS:
        return score_reasoning_dimension(module_name, result)

    raise KeyError(f"No scoring function is defined for module {module_name!r}.")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
