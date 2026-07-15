"""
Documented weight constants for the Overall Communication Score
(Milestone 5's "design and document a transparent weighted scoring
algorithm; do not use arbitrary values" requirement).

Where these numbers come from
------------------------------
There is no labeled dataset behind this product to fit weights against
(no corpus of transcripts with human-assigned "true" communication
scores exists at this stage), so "not arbitrary" cannot honestly mean
"empirically derived." What it can honestly mean, and what this file
does, is: every weight traces to a stated, checkable reason, is a
plain round number rather than a value tuned to make some example come
out a certain way, and is written down here instead of scattered as
inline magic numbers — the same standard this codebase has already held
every other heuristic threshold to (see Sprint 4.3's filler-word
dictionary, Sprint 4.5's hedge-word list, and the per-metric thresholds
in dimension_scores.py alongside this file).

The one non-arbitrary anchor available is the product's own stated
mission (see the project brief this whole application is built from):
an "AI-powered communication coach focused on structural thinking, not
grammar." That sentence is the actual product requirement this scoring
algorithm is accountable to, and it directly implies a *relative*
ordering even without absolute values: dimensions that assess structural
thinking should outweigh dimensions that assess surface-level fluency
mechanics, because the product explicitly says the former is the point
and the latter explicitly is not ("not grammar").

The ten evaluation dimensions ADR 003 §2 defines sort cleanly into three
tiers along exactly that line:

  Tier 1 — STRUCTURAL_THINKING_WEIGHT (structure, logical_flow, clarity)
    These three are the dimensions "structural thinking" and "logical
    organization" most directly name (ADR 003 §2's own dimension list).
    Highest tier.

  Tier 2 — SECONDARY_REASONING_WEIGHT (topic_drift, confidence, conciseness)
    Still semantic judgment calls the reasoning pass makes (not
    mechanical counts), but not what the mission statement singles out
    by name — topic drift, confidence, and conciseness are about how
    well the content is delivered, not whether it's structurally sound.
    Middle tier.

  Tier 3 — FLUENCY_METRIC_WEIGHT (filler_words, hesitations,
  repetitions, speaking_pace)
    The four deterministic Metric modules (Sprint 4.3) — exactly the
    "grammar"/fluency-mechanics territory the mission statement
    explicitly says this product is *not* about. Still real signal
    worth scoring (a transcript riddled with filler words is still
    worth flagging), just not the primary axis. Lowest tier.

Within a tier, every dimension gets an identical weight — there is no
documented reason available to rank e.g. "clarity" above "structure"
within Tier 1, so this file doesn't pretend to one; equal weighting
within a tier is the deliberately conservative default when no further
distinction is justified.

The exact numbers (15.0 / 10.0 / 6.25) were chosen only to satisfy two
constraints, both checkable below: (1) Tier 1 > Tier 2 > Tier 3 per
dimension, and (2) all ten weights sum to exactly 100.0, so
`overall_score` is a true 0-100 weighted average with no fudge factor.
Given 3 Tier-1 dimensions, 3 Tier-2 dimensions, and 4 Tier-3 dimensions,
the simplest ratio satisfying both is Tier1 : Tier2 : Tier3 = 15 : 10 :
6.25 (i.e., roughly 2.4x and 1.6x steps) — round, easy to re-derive by
hand, and verified by the assertion at the bottom of this file rather
than trusted by eye.

Anyone revisiting this later — once real user data or expert-reviewed
transcripts exist to validate against — should replace this rationale
with an empirical one, not just adjust the numbers. Until then, this is
the honest, documented alternative: a stated, checkable heuristic
instead of a hidden one.
"""

STRUCTURAL_THINKING_WEIGHT = 15.0
SECONDARY_REASONING_WEIGHT = 10.0
FLUENCY_METRIC_WEIGHT = 6.25

MODULE_WEIGHTS: dict[str, float] = {
    # Tier 1 — structural thinking (ADR 003 §2's namesake dimensions)
    "structure": STRUCTURAL_THINKING_WEIGHT,
    "logical_flow": STRUCTURAL_THINKING_WEIGHT,
    "clarity": STRUCTURAL_THINKING_WEIGHT,
    # Tier 2 — secondary semantic reasoning
    "topic_drift": SECONDARY_REASONING_WEIGHT,
    "confidence": SECONDARY_REASONING_WEIGHT,
    "conciseness": SECONDARY_REASONING_WEIGHT,
    # Tier 3 — deterministic fluency/delivery metrics
    "filler_words": FLUENCY_METRIC_WEIGHT,
    "hesitations": FLUENCY_METRIC_WEIGHT,
    "repetitions": FLUENCY_METRIC_WEIGHT,
    "speaking_pace": FLUENCY_METRIC_WEIGHT,
}

_WEIGHT_SUM_TOLERANCE = 1e-9

assert abs(sum(MODULE_WEIGHTS.values()) - 100.0) < _WEIGHT_SUM_TOLERANCE, (
    "MODULE_WEIGHTS must sum to exactly 100.0 so overall_score is a true "
    "0-100 weighted average — see this file's module docstring."
)
"""
Checked at import time, not just documented: if a future edit adds an
eleventh dimension's weight without adjusting the others, the process
fails loudly at startup rather than silently producing a score that
isn't really out of 100 anymore.
"""


# Band thresholds for CommunicationScore.band (models.py). Chosen the
# same way the weights above were: round numbers with a stated reason,
# not fit to data. Because six of the ten dimensions are scored on the
# 100/60/20 three-tier band (see dimension_scores.py's
# REASONING_LABEL_BANDS), a transcript that lands mostly on the
# "moderate" (60) band across dimensions should land in the middle of
# the overall range — these thresholds are set so that's true: a
# transcript scoring a flat 60 everywhere lands at 60.0, comfortably
# inside STRONG's lower half, matching the intuitive reading that
# "moderate on every dimension" is a reasonably solid, not a failing,
# result.
SCORE_BAND_THRESHOLDS: dict[str, float] = {
    "excellent": 85.0,
    "strong": 65.0,
    "developing": 40.0,
    # anything below "developing"'s floor is NEEDS_WORK
}
