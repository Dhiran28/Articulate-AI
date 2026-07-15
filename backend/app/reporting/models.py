"""
CommunicationReport (Milestone 5) — the one unified report schema
POST /analyze returns. Deliberately a thin composition of already-typed
pieces (`AnalysisReport`, `CommunicationScore`, `CoachingReport`) rather
than a flattened, re-invented shape: every field here is exactly the
same pydantic model its owning engine already produces and already has
its own tests for, so this package adds no new domain logic of its
own — see engine.py, which is correspondingly thin.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.analysis.models import AnalysisReport
from app.coaching.models import CoachingReport
from app.scoring.models import CommunicationScore


class CommunicationReport(BaseModel):
    """
    The single response shape for `POST /analyze`.

    - `analysis`: the CIE's complete, descriptive-only output (every
      Metric and Reasoning module's result, evidence included) — ADR
      003's `AnalysisReport`.
    - `score`: the Overall Communication Score and its full, transparent
      per-module breakdown — see app/scoring/README.md for the algorithm.
    - `coaching`: strengths, weaknesses, recommendations, suggested
      exercises, and next practice focus — ADR 003's `CoachingReport`.
    - `executive_summary`: the dashboard-ready summary text
      (`CommunicationSummaryGenerator`'s output), surfaced at the top
      level since it's the one field most likely to be read on its own
      without unpacking the rest of the report.
    """

    transcript_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    executive_summary: str
    score: CommunicationScore
    analysis: AnalysisReport
    coaching: CoachingReport
