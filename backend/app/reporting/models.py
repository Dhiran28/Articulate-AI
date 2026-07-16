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


class PromptVersions(BaseModel):
    """
    Which version of each real prompt this application ships with
    produced this report (Milestone 5.1) — read directly off
    `PromptTemplate.metadata.version` (app/llm/prompt_loader.py) for
    whichever prompt id `ReasoningPass`/`CoachingEngine` are configured
    to use, not off anything the LLM call itself returned. Reproducing a
    result later ("this report came from reasoning_pass_v1 @ 1.1.0")
    only requires this field plus the report's own content — never the
    raw provider response, which this codebase has never persisted.

    `None` for a field means that stage's LLM call never actually ran
    for this report (no provider configured, or that stage's own
    documented failure mode) — not that versioning is broken. A prompt
    that's registered but never called still has a version; a report
    only cites the version of a prompt actually used to produce it, so
    an unreachable stage's version is honestly absent rather than
    misleadingly filled in from the registry anyway.
    """

    reasoning_pass: str | None = None
    coaching: str | None = None


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
    - `prompt_versions` (Milestone 5.1): provenance for the two LLM calls
      this report can reflect — see `PromptVersions` above.
    - `transcript` (Milestone 6): the verbatim processed transcript text
      (`TranscriptProcessingResult.processed_transcript.text` —
      unmodified from Sprint 3.5's "preserve, don't clean" transcript,
      the same text every metric/reasoning module already read). Added
      as a scoped, explicitly-approved exception to Milestone 6's
      otherwise-frozen backend: the frontend's Transcript Viewer has no
      other way to obtain this text, since `/analyze` accepts audio and
      never otherwise returns the words spoken. Purely additive — no
      existing field, endpoint, or engine interface changed to add it;
      `ReportBuilder.build()`'s new `transcript` parameter is required
      (unlike `prompt_versions`, which stayed optional) since every real
      `/analyze` response has processed a transcript by the time
      `ReportBuilder` runs.
    """

    transcript_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    executive_summary: str
    transcript: str
    score: CommunicationScore
    analysis: AnalysisReport
    coaching: CoachingReport
    prompt_versions: PromptVersions = Field(default_factory=PromptVersions)
