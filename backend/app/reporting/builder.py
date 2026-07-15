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

from .models import CommunicationReport
from app.scoring.models import CommunicationScore


class ReportBuilder:
    def build(
        self,
        *,
        transcript_id: str,
        analysis: AnalysisReport,
        score: CommunicationScore,
        coaching: CoachingReport,
        executive_summary: str,
    ) -> CommunicationReport:
        return CommunicationReport(
            transcript_id=transcript_id,
            executive_summary=executive_summary,
            score=score,
            analysis=analysis,
            coaching=coaching,
        )
