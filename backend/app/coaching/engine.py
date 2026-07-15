"""
CoachingEngine (Milestone 5) — ADR 003 §1/§2's deferred second engine,
built. Consumes a finished `AnalysisReport` (the CIE's sole output) and
produces a `CoachingReport`: strengths, weaknesses, actionable
recommendations, suggested exercises, next practice focus, and an
executive summary. Never reads the transcript directly — everything it
knows about the session comes from the already-structured report, the
same architectural guarantee ADR 003 §5 named ("the Coaching Engine
*cannot* invent an observation the CIE didn't already surface").

Reuses `app/llm`'s `LLMReasoner` exactly the way `ReasoningPass` does —
one call, one schema, one validation pass — rather than introducing a
second LLM integration pattern for this second engine.
"""

import json
import logging

from app.analysis.models import AnalysisReport, ModuleResult, ModuleStatus
from app.llm.errors import LLMError
from app.llm.reasoner import LLMReasoner

from .errors import CoachingError, CoachingErrorReason
from .models import CoachingContent, CoachingReport

logger = logging.getLogger(__name__)


class CoachingEngine:
    def __init__(self, reasoner: LLMReasoner | None, prompt_id: str = "coaching_v1") -> None:
        """
        `reasoner` is `LLMReasoner | None`, not a required `LLMReasoner`
        — mirroring `ModuleRegistry`'s own `reasoning_pass: ReasoningPass
        | None = None` (app/analysis/registry.py). A server with no LLM
        provider configured can still serve metric-only analysis; the
        Coaching Engine should fail the same documented, specific way
        (`NO_PROVIDER_CONFIGURED`) rather than never having been
        constructible in the first place.
        """
        self._reasoner = reasoner
        self.prompt_id = prompt_id

    async def generate(self, report: AnalysisReport) -> CoachingReport:
        ok_modules = {name: r for name, r in report.modules.items() if r.status is ModuleStatus.OK}
        failed_modules = sorted(name for name, r in report.modules.items() if r.status is ModuleStatus.FAILED)

        if not ok_modules:
            raise CoachingError(
                CoachingErrorReason.NOTHING_TO_COACH,
                "No analysis modules succeeded for this transcript, so no coaching can be generated.",
            )

        if self._reasoner is None:
            raise CoachingError(
                CoachingErrorReason.NO_PROVIDER_CONFIGURED,
                "No LLM reasoner is configured on the server.",
            )

        template_context = {"analysis_report_json": self._serialize(ok_modules)}

        try:
            content = await self._reasoner.reason(self.prompt_id, template_context, CoachingContent)
        except LLMError as exc:
            # Same direct, lossless mapping used everywhere else an
            # LLMError crosses a domain boundary (see
            # app/analysis/modules/reasoning_base.py, registry.py) —
            # CoachingErrorReason's five LLM-related values share
            # identical string values with LLMErrorReason by design.
            raise CoachingError(CoachingErrorReason(exc.reason.value), exc.message) from exc

        unavailable = [
            f"{module_name} could not be assessed for this session (analysis error)."
            for module_name in failed_modules
        ]

        return CoachingReport(
            transcript_id=report.transcript_id,
            unavailable=unavailable,
            **content.model_dump(),
        )

    def _serialize(self, ok_modules: dict[str, ModuleResult]) -> str:
        """
        Turns every successful module's structured result into plain
        JSON text for the coaching prompt's `$analysis_report_json`
        variable — never the transcript itself (see this class's own
        docstring). Deliberately includes every module's `module_name`
        as the JSON key, since the coaching prompt is instructed to cite
        that exact key back in `based_on_module` for every strength,
        weakness, and recommendation it produces.
        """
        payload: dict[str, dict] = {}
        for module_name, result in ok_modules.items():
            if result.metric is not None:
                payload[module_name] = {
                    "type": "metric",
                    "value": result.metric.value,
                    "unit": result.metric.unit,
                    "details": result.metric.details,
                }
            elif result.reasoning is not None:
                payload[module_name] = {
                    "type": "reasoning",
                    "label": result.reasoning.label,
                    "explanation": result.reasoning.explanation,
                    "evidence": result.reasoning.evidence,
                }
        return json.dumps(payload, indent=2, default=str)
