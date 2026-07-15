"""
Tests for the Report Builder (Milestone 5): app/reporting/{builder,models}.py.

See tests/README.md for how this file fits into the overall suite.
"""

from app.analysis.models import AnalysisReport
from app.coaching.models import CoachingReport
from app.reporting.builder import ReportBuilder
from app.reporting.models import CommunicationReport
from app.scoring.models import CommunicationScore, ScoreBand


def _coaching_report() -> CoachingReport:
    return CoachingReport(
        transcript_id="t-1",
        strengths=[],
        weaknesses=[],
        recommendations=[],
        suggested_exercises=[],
        next_practice_focus="Focus on pacing.",
        executive_summary="Solid session overall.",
    )


def _score() -> CommunicationScore:
    return CommunicationScore(overall_score=72.5, band=ScoreBand.STRONG, module_scores=[], unscored_modules=[])


class TestReportBuilder:
    def test_builds_a_complete_communication_report(self) -> None:
        builder = ReportBuilder()
        analysis = AnalysisReport(transcript_id="t-1")

        report = builder.build(
            transcript_id="t-1",
            analysis=analysis,
            score=_score(),
            coaching=_coaching_report(),
            executive_summary="Dashboard-ready summary.",
        )

        assert isinstance(report, CommunicationReport)
        assert report.transcript_id == "t-1"
        assert report.executive_summary == "Dashboard-ready summary."
        assert report.score.overall_score == 72.5
        assert report.analysis is analysis
        assert report.coaching.next_practice_focus == "Focus on pacing."

    def test_does_not_mutate_any_input(self) -> None:
        builder = ReportBuilder()
        analysis = AnalysisReport(transcript_id="t-1")
        score = _score()
        coaching = _coaching_report()

        before_analysis = analysis.model_copy(deep=True)
        before_score = score.model_copy(deep=True)
        before_coaching = coaching.model_copy(deep=True)

        builder.build(
            transcript_id="t-1", analysis=analysis, score=score, coaching=coaching, executive_summary="x"
        )

        assert analysis == before_analysis
        assert score == before_score
        assert coaching == before_coaching

    def test_serializes_to_json_cleanly(self) -> None:
        # A sanity check that the composed model round-trips through
        # FastAPI's own serialization path without error — the actual
        # HTTP-level contract is exercised end-to-end in
        # test_analyze_endpoint.py.
        builder = ReportBuilder()
        report = builder.build(
            transcript_id="t-1",
            analysis=AnalysisReport(transcript_id="t-1"),
            score=_score(),
            coaching=_coaching_report(),
            executive_summary="x",
        )

        dumped = report.model_dump_json()
        assert '"transcript_id":"t-1"' in dumped.replace(" ", "")
