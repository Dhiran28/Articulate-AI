"""
ScoringEngine (Milestone 5): turns a finished AnalysisReport into one
CommunicationScore. Reads the report only — never re-analyzes the
transcript, never calls a module or the LLM itself — the same
"consumes the finished, structured report" relationship the Coaching
Engine has to the CIE (ADR 003 §1).
"""

from .dimension_scores import score_module
from .errors import ScoringError, ScoringErrorReason
from .models import CommunicationScore, ModuleScore, ScoreBand
from .weights import MODULE_WEIGHTS, SCORE_BAND_THRESHOLDS

from app.analysis.models import AnalysisReport, ModuleStatus


class ScoringEngine:
    def score(self, report: AnalysisReport) -> CommunicationScore:
        module_scores: list[ModuleScore] = []
        unscored: list[str] = []

        for module_name, nominal_weight in MODULE_WEIGHTS.items():
            result = report.modules.get(module_name)

            if result is None or result.status is not ModuleStatus.OK:
                unscored.append(module_name)
                continue

            score_value, driver = score_module(module_name, result)
            module_scores.append(
                ModuleScore(
                    module_name=module_name,
                    score=score_value,
                    nominal_weight=nominal_weight,
                    effective_weight=nominal_weight,  # renormalized below
                    driver=driver,
                )
            )

        if not module_scores:
            raise ScoringError(
                ScoringErrorReason.NO_SCORABLE_MODULES,
                "None of the modules this scoring algorithm knows how to weigh "
                "succeeded for this transcript, so no Overall Communication "
                "Score can be computed.",
            )

        # Renormalize: a module that failed contributes no score, and its
        # documented weight is redistributed proportionally among the
        # modules that did succeed, rather than silently treating a
        # missing module as a 0 (which would conflate "this module
        # couldn't run" with "this module ran and scored terribly" —
        # two very different situations that should not look the same
        # in the final number).
        total_nominal_weight_used = sum(m.nominal_weight for m in module_scores)
        for module_score in module_scores:
            module_score.effective_weight = (module_score.nominal_weight / total_nominal_weight_used) * 100.0

        overall_score = sum(m.score * m.effective_weight for m in module_scores) / 100.0
        overall_score = round(overall_score, 1)

        return CommunicationScore(
            overall_score=overall_score,
            band=self._band_for(overall_score),
            module_scores=module_scores,
            unscored_modules=unscored,
        )

    def _band_for(self, overall_score: float) -> ScoreBand:
        if overall_score >= SCORE_BAND_THRESHOLDS["excellent"]:
            return ScoreBand.EXCELLENT
        if overall_score >= SCORE_BAND_THRESHOLDS["strong"]:
            return ScoreBand.STRONG
        if overall_score >= SCORE_BAND_THRESHOLDS["developing"]:
            return ScoreBand.DEVELOPING
        return ScoreBand.NEEDS_WORK
