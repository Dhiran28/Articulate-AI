"""
POST /analyze (Milestone 5) — the single public analysis API.

Runs the complete pipeline in one request: Audio -> Transcription ->
Metric Analysis -> Shared Reasoning Pass -> Coaching -> Report Builder
-> JSON response. Every stage is an already-built, already-tested
component from a previous sprint, reused through its existing public
interface — this route adds no analysis, scoring, or coaching logic of
its own, only orchestration and HTTP error mapping, the same "thin
route, real logic lives in a service/engine" discipline every other
route in this codebase already follows (see upload.py, transcribe.py).

This single endpoint deliberately replaces the two-step
upload-then-transcribe flow (POST /api/upload, then POST
/api/upload/{id}/transcribe) with one call for a caller that wants the
full pipeline and doesn't need the intermediate audio asset or raw
transcript on their own. Those two routes are untouched and still work
standalone — nothing about this route changes them.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.analysis.engine import AnalysisEngine
from app.analysis.errors import AnalysisError, AnalysisErrorReason
from app.audio.errors import AudioValidationError, AudioValidationReason
from app.audio.ingestors.http_upload import HttpUploadIngestor
from app.audio.service import AudioService
from app.coaching.engine import CoachingEngine
from app.coaching.errors import CoachingError, CoachingErrorReason
from app.coaching.summary import CommunicationSummaryGenerator
from app.core.dependencies import (
    get_analysis_engine,
    get_audio_service,
    get_coaching_engine,
    get_report_builder,
    get_scoring_engine,
    get_summary_generator,
    get_transcript_processor,
    get_transcription_service,
)
from app.reporting.builder import ReportBuilder
from app.reporting.models import CommunicationReport
from app.scoring.engine import ScoringEngine
from app.scoring.errors import ScoringError, ScoringErrorReason
from app.transcription.errors import TranscriptionError, TranscriptionErrorReason
from app.transcription.service import TranscriptionService
from app.transcript_processing.processor import TranscriptProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])

# Mirrors upload.py's and transcribe.py's own reason-to-status maps —
# kept local rather than imported so this route's HTTP contract doesn't
# silently change if either of those private maps is edited for
# unrelated reasons.
_AUDIO_REASON_TO_STATUS: dict[AudioValidationReason, int] = {
    AudioValidationReason.UNSUPPORTED_FORMAT: 400,
    AudioValidationReason.EMPTY_FILE: 400,
    AudioValidationReason.FILE_TOO_LARGE: 413,
}

_TRANSCRIPTION_REASON_TO_STATUS: dict[TranscriptionErrorReason, int] = {
    TranscriptionErrorReason.ASSET_NOT_FOUND: 404,
    TranscriptionErrorReason.PROVIDER_MISCONFIGURED: 503,
    TranscriptionErrorReason.PROVIDER_ERROR: 502,
}

_ANALYSIS_REASON_TO_STATUS: dict[AnalysisErrorReason, int] = {
    AnalysisErrorReason.TRANSCRIPT_EMPTY: 422,
}

_SCORING_REASON_TO_STATUS: dict[ScoringErrorReason, int] = {
    # Only reachable if every weighted module failed — an unexpected,
    # whole-pipeline condition rather than a normal degraded state (a
    # missing LLM provider alone still leaves the four Metric modules
    # scorable), so this maps to 500, not a 4xx.
    ScoringErrorReason.NO_SCORABLE_MODULES: 500,
}

_COACHING_REASON_TO_STATUS: dict[CoachingErrorReason, int] = {
    CoachingErrorReason.NOTHING_TO_COACH: 422,
    CoachingErrorReason.LLM_TIMEOUT: 504,
    CoachingErrorReason.LLM_PROVIDER_ERROR: 502,
    CoachingErrorReason.LLM_INVALID_RESPONSE: 502,
    CoachingErrorReason.LLM_SCHEMA_ERROR: 502,
    CoachingErrorReason.PROMPT_NOT_FOUND: 500,
    CoachingErrorReason.NO_PROVIDER_CONFIGURED: 503,
}


@router.post("/analyze", response_model=CommunicationReport, status_code=201)
async def analyze(
    file: UploadFile = File(...),
    audio_service: AudioService = Depends(get_audio_service),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    processor: TranscriptProcessor = Depends(get_transcript_processor),
    analysis_engine: AnalysisEngine = Depends(get_analysis_engine),
    scoring_engine: ScoringEngine = Depends(get_scoring_engine),
    coaching_engine: CoachingEngine = Depends(get_coaching_engine),
    summary_generator: CommunicationSummaryGenerator = Depends(get_summary_generator),
    report_builder: ReportBuilder = Depends(get_report_builder),
) -> CommunicationReport:
    """
    Accepts one audio file and returns one complete `CommunicationReport`.

    Pipeline (each stage reuses its existing, already-tested component
    unchanged — see this module's own docstring):

      1. `AudioService.ingest` — validate and store the upload (same
         validation POST /api/upload applies: format, size, non-empty).
      2. `TranscriptionService.transcribe_asset` — send the stored audio
         to the configured transcription provider.
      3. `TranscriptProcessor.process` — turn the raw transcription into
         a processed transcript + metadata, unmodified from Sprint 3.5.
      4. `AnalysisEngine.run` — the Communication Intelligence Engine:
         all four Metric modules, then (if an LLM reasoner is
         configured) the one shared Reasoning Pass call, then all six
         Reasoning modules reading their section of it. Per-module
         failure isolation applies exactly as it does standalone (ADR
         003 §7) — a missing LLM provider degrades every REASONING
         module's result to a specific, documented failure reason
         rather than failing this whole request.
      5. `ScoringEngine.score` — the Overall Communication Score,
         computed only from whichever modules in step 4 actually
         succeeded (see app/scoring/README.md for the weighting
         algorithm).
      6. `CoachingEngine.generate` — strengths, weaknesses,
         recommendations, suggested exercises, next practice focus, and
         the raw executive summary text, from one LLM call over the
         finished analysis report (never the transcript itself).
      7. `CommunicationSummaryGenerator.generate` — the coaching
         engine's raw executive summary, formatted for dashboard
         display.
      8. `ReportBuilder.build` — assembles the above into one
         `CommunicationReport` and returns it.

    A failure at step 4, 5, or 6 that isn't the whole-request guard
    conditions below still produces a mix of `ok`/`failed` results
    inside `analysis.modules` (step 4) or a specific coaching failure
    (steps 5/6) — this route only raises an HTTPException for
    conditions that mean no meaningful report can be built at all.
    """
    ingestor = HttpUploadIngestor(file)
    raw_upload = await ingestor.ingest()

    try:
        asset = await audio_service.ingest(raw_upload)
    except AudioValidationError as exc:
        raise HTTPException(
            status_code=_AUDIO_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    try:
        raw_transcript = await transcription_service.transcribe_asset(asset.id)
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=_TRANSCRIPTION_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    processed_transcript = processor.process(raw_transcript)

    try:
        analysis_report = await analysis_engine.run(asset.id, processed_transcript)
    except AnalysisError as exc:
        raise HTTPException(
            status_code=_ANALYSIS_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    try:
        score = scoring_engine.score(analysis_report)
    except ScoringError as exc:
        raise HTTPException(
            status_code=_SCORING_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    try:
        coaching_report = await coaching_engine.generate(analysis_report)
    except CoachingError as exc:
        raise HTTPException(
            status_code=_COACHING_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    executive_summary = summary_generator.generate(coaching_report)

    return report_builder.build(
        transcript_id=asset.id,
        analysis=analysis_report,
        score=score,
        coaching=coaching_report,
        executive_summary=executive_summary,
    )
