# Scoring (Milestone 5)

`app/scoring/` turns a finished `AnalysisReport` (the Communication
Intelligence Engine's sole output — ADR 003) into one Overall
Communication Score. Reads the report only — never re-analyzes the
transcript, never calls a module or the LLM itself. See
`docs/decisions/004-*.md` §4 for the full design writeup; this file is
the package-level reference.

## Folder structure

```
backend/app/scoring/
├── models.py            # CommunicationScore, ModuleScore, ScoreBand
├── errors.py             # ScoringErrorReason, ScoringError
├── weights.py             # MODULE_WEIGHTS — documented, non-arbitrary weights (READ THIS FIRST)
├── dimension_scores.py    # per-module scoring functions + their documented thresholds
└── engine.py               # ScoringEngine
```

## Why weights.py is the file to read first

The whole "design and document a transparent weighted scoring
algorithm; do not use arbitrary values" requirement lives in that one
file's module docstring — every weight traces to a stated reason (the
product's own mission statement: "structural thinking, not grammar"),
not a number picked to make an example look right. `dimension_scores.py`
holds the same standard for each individual formula (why 10 fillers per
100 words is the ceiling, why 120-160 wpm is the ideal pace band, etc.)
— every threshold there is disclosed as a heuristic, not empirically
fit, because no labeled dataset exists yet for this product.

## The algorithm, in one paragraph

Every one of the ten weighted dimensions (four deterministic Metric
modules, six semantic Reasoning modules) is converted to a 0-100
sub-score by its own documented formula. Metric modules get a real
formula over their numeric output. Reasoning modules — which carry no
numeric score at all by design (ADR 003's "no scores" requirement) —
are scored via a fixed three-value label vocabulary
(`reasoning_pass_v1.md` constrains the LLM to always pick one of three
per dimension) mapped onto three shared anchor scores: 100 / 60 / 20.
Each sub-score is multiplied by its documented weight (`weights.py`);
weights sum to exactly 100.0, checked at import time. A module that
failed or never ran is excluded, and its weight is redistributed
proportionally among whatever did succeed — never silently treated as
a zero.

## Failure modes

- **A module missing or `status != OK`:** excluded, weight
  redistributed — see `ScoringEngine.score()`.
- **`ScoringErrorReason.NO_SCORABLE_MODULES`:** raised only if literally
  every weighted module failed or never ran — nothing to compute a
  score from at all. The one whole-request failure this package has;
  everything else degrades per-module.

## Transparency

`CommunicationScore.module_scores` (one `ModuleScore` per contributing
module) exposes the sub-score, the nominal (documented) weight, the
effective (renormalized) weight, and a human-readable `driver` string
— a caller can audit the entire computation from the API response
alone.

## How a future dimension gets added

1. Add its weight to `MODULE_WEIGHTS` in `weights.py`, in the
   appropriate tier (or a new one, with the same documented
   justification standard the existing three tiers hold themselves to)
   — the assertion at the bottom of that file will fail loudly if the
   new total isn't still 100.0.
2. Add a scoring function to `dimension_scores.py` (a metric formula, or
   a label-band dict if it's a reasoning dimension) and register it in
   `_METRIC_SCORERS` or `REASONING_LABEL_BANDS`.
3. Nothing in `engine.py` changes — `ScoringEngine.score()` iterates
   `MODULE_WEIGHTS` generically and dispatches through `score_module()`,
   the same "registry-driven, not hardcoded" pattern `ModuleRegistry`
   already established for modules themselves.
