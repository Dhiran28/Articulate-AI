"""
ReportBuilder (Milestone 5) — deliberately dumb assembly, no business
logic of its own. Every real decision (what the analysis says, what the
score is, what the coaching says, what the dashboard summary reads)
already happened in the engine that produced each piece; this class's
only job is packaging them into one `CommunicationReport`, the same
"engine.py deliberately thin" discipline `AnalysisEngine` and
`ReasoningPass` already hold themselves to.
"""

from app.analysis.models import AnalysisReport
from app.coaching.models import CoachingReport

from .models import CommunicationReport, PromptVersions
from app.scoring.models import CommunicationScore


class ReportBuilder:
    def build(
        self,
        *,
        transcript_id: str,
        transcript: str,
        analysis: AnalysisReport,
        score: CommunicationScore,
        coaching: CoachingReport,
        executive_summary: str,
        prompt_versions: PromptVersions | None = None,
    ) -> CommunicationReport:
        # Milestone 5.1: prompt_versions is optional, defaulting to
        # "nothing known" (both fields None) rather than requiring every
        # existing caller of this method to start supplying it —
        # additive, not a breaking change to this builder's contract.
        #
        # Milestone 6: `transcript` is required, not optional — unlike
        # prompt_versions, every real call site already has a processed
        # transcript in hand by the time ReportBuilder runs (see
        # app/api/analyze.py), so there's no legitimate "unknown"
        # transcript state to default to.
        return CommunicationReport(
            transcript_id=transcript_id,
            executive_summary=executive_summary,
            transcript=transcript,
            score=score,
            analysis=analysis,
            coaching=coaching,
            prompt_versions=prompt_versions or PromptVersions(),
        )
