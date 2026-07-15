"""
Scoring's own typed shapes (Milestone 5) — kept separate from
app/analysis/models.py the same way app/coaching's models are kept
separate from it: this package interprets an already-finished
AnalysisReport, it does not extend the CIE's own descriptive-only output
contract.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ScoreBand(str, Enum):
    """
    A coarse, human-facing label for the numeric overall_score, on top
    of the number itself — see weights.py for exactly where the
    thresholds come from and why.
    """

    EXCELLENT = "excellent"
    STRONG = "strong"
    DEVELOPING = "developing"
    NEEDS_WORK = "needs_work"


class ModuleScore(BaseModel):
    """
    One module's contribution to the overall score — kept fully
    transparent (this is the whole point of the "transparent weighted
    scoring algorithm" requirement): every number the final
    `overall_score` was built from is visible here, not just the total.
    """

    module_name: str
    score: float
    """This module's own 0-100 sub-score, before weighting."""

    nominal_weight: float
    """
    This module's documented weight out of 100 (see weights.py's
    MODULE_WEIGHTS) — fixed, independent of which other modules
    happened to succeed this run.
    """

    effective_weight: float
    """
    The weight actually used in the final weighted sum, after
    renormalizing `nominal_weight` against only the modules that were
    actually scorable this run (see engine.py). Equal to
    `nominal_weight` whenever every module succeeded.
    """

    driver: str
    """
    A short, human-readable statement of what specifically produced
    `score` (e.g. "4.2 fillers per 100 words", or a reasoning label like
    "clear_structure") — so a caller can see *why* a module scored the
    way it did without re-deriving it from raw ModuleResult data.
    """


class CommunicationScore(BaseModel):
    """
    The Overall Communication Score (Milestone 5) — one number plus the
    fully transparent breakdown that produced it.
    """

    overall_score: float
    """0-100, rounded to one decimal place."""

    band: ScoreBand

    module_scores: list[ModuleScore] = Field(default_factory=list)
    """Every module that actually contributed to `overall_score`, in
    weights.py's documented order."""

    unscored_modules: list[str] = Field(default_factory=list)
    """
    Modules weights.py has a documented weight for, but that were
    missing from the AnalysisReport or had `status != OK` this run —
    excluded from `overall_score` entirely (their weight was
    redistributed to the modules that did succeed), not silently
    counted as zero.
    """
