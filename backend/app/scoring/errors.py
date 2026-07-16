"""
Scoring's error vocabulary (Milestone 5) — same reason/message pattern
as every other error type in this codebase (AnalysisError, LLMError,
CoachingError, ...).
"""

from enum import Enum


class ScoringErrorReason(str, Enum):
    # Every module the scoring algorithm knows how to weigh (see
    # weights.py) either wasn't registered, didn't run, or failed —
    # there is nothing to compute an Overall Communication Score from.
    # Distinct from CoachingErrorReason.NOTHING_TO_COACH, which is the
    # same underlying condition surfaced by a different consumer of the
    # same AnalysisReport.
    NO_SCORABLE_MODULES = "no_scorable_modules"

    # RC1 hardening: score_module() (dimension_scores.py) dispatches on
    # module_name against two independently-maintained lookup tables
    # (_METRIC_SCORERS, REASONING_LABEL_BANDS). If a module name is ever
    # registered in MODULE_WEIGHTS (weights.py) without a matching entry
    # in one of those two tables — a configuration drift, not a runtime
    # data problem — score_module() used to raise a bare KeyError that
    # ScoringEngine.score() didn't catch, which would reach the /analyze
    # route as an unstructured 500 instead of the same clean error shape
    # every other scoring failure gets. See ScoringEngine.score().
    NO_SCORER_FOR_MODULE = "no_scorer_for_module"


class ScoringError(Exception):
    """
    Raised only when literally nothing in the AnalysisReport can be
    scored — every other case (some modules failed, some succeeded) is
    handled by renormalizing weights across whatever succeeded (see
    engine.py), not by raising. Mirrors AnalysisError's own scope: a
    whole-request guard condition, not a per-module failure.
    """

    def __init__(self, reason: ScoringErrorReason, message: str) -> None:
        self.reason = reason
        self.message = message
        super().__init__(message)
