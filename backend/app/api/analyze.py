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

Milestone 6 note: the response's `transcript` field (see
app/reporting/models.py's `CommunicationReport`) is the one explicitly
approved, purely additive exception to that milestone's otherwise-frozen
backend — the frontend's Transcript Viewer has no other way to obtain
this text. `processed_transcript.processed_transcript.text` was already
computed here, on this exact line, before Milestone 6 existed; this only
threads it into the final report instead of leaving it unused after
`AnalysisEngine.run()` reads it.
"""

import logging
import time

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
    get_prompt_registry,
    get_report_builder,
    get_scoring_engine,
    get_summary_generator,
    get_transcript_processor,
    get_transcription_service,
)
from app.llm.errors import PromptNotFoundError
from app.llm.prompt_registry import PromptRegistry
from app.reporting.builder import ReportBuilder
from app.reporting.models import CommunicationReport, PromptVersions
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
    # Also a configuration-drift condition, not a user-facing input
    # problem — see ScoringErrorReason.NO_SCORER_FOR_MODULE's docstring.
    ScoringErrorReason.NO_SCORER_FOR_MODULE: 500,
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
    prompt_registry: PromptRegistry = Depends(get_prompt_registry),
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
    request_start = time.monotonic()
    ingestor = HttpUploadIngestor(file)
    raw_upload = await ingestor.ingest()

    try:
        asset = await audio_service.ingest(raw_upload)
    except AudioValidationError as exc:
        raise HTTPException(
            status_code=_AUDIO_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    logger.info("analyze_request_started session_id=%s", asset.id)

    try:
        raw_transcript = await transcription_service.transcribe_asset(asset.id)
    except TranscriptionError as exc:
        logger.error("analyze_request_failed session_id=%s stage=transcription reason=%s", asset.id, exc.reason.value)
        raise HTTPException(
            status_code=_TRANSCRIPTION_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    processed_transcript = processor.process(raw_transcript)

    try:
        # session_id flows through AnalysisContext.reasoning_context (the
        # extensibility hook Sprint 4.5 built for exactly this kind of
        # addition) so ReasoningPass can attach it to its one LLM call's
        # log line — see app/analysis/reasoning_pass/batch.py.
        analysis_report = await analysis_engine.run(
            asset.id, processed_transcript, reasoning_context={"session_id": asset.id}
        )
    except AnalysisError as exc:
        logger.error("analyze_request_failed session_id=%s stage=analysis reason=%s", asset.id, exc.reason.value)
        raise HTTPException(
            status_code=_ANALYSIS_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    try:
        score = scoring_engine.score(analysis_report)
    except ScoringError as exc:
        logger.error("analyze_request_failed session_id=%s stage=scoring reason=%s", asset.id, exc.reason.value)
        raise HTTPException(
            status_code=_SCORING_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    try:
        coaching_report = await coaching_engine.generate(analysis_report)
    except CoachingError as exc:
        logger.error("analyze_request_failed session_id=%s stage=coaching reason=%s", asset.id, exc.reason.value)
        raise HTTPException(
            status_code=_COACHING_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    executive_summary = summary_generator.generate(coaching_report)

    report = report_builder.build(
        transcript_id=asset.id,
        transcript=processed_transcript.processed_transcript.text,
        analysis=analysis_report,
        score=score,
        coaching=coaching_report,
        executive_summary=executive_summary,
        prompt_versions=_resolve_prompt_versions(prompt_registry),
    )

    logger.info(
        "analyze_request_completed session_id=%s total_latency_ms=%.1f",
        asset.id,
        (time.monotonic() - request_start) * 1000,
    )
    return report


def _resolve_prompt_versions(prompt_registry: PromptRegistry) -> PromptVersions:
    """
    Reads each real prompt's declared version straight off the registry
    (`PromptTemplate.metadata.version` — app/llm/prompt_loader.py), for
    whichever prompt id `ReasoningPass`/`CoachingEngine` are configured
    to use by default. `PromptNotFoundError` shouldn't happen in a
    correctly deployed server (`get_prompt_registry()` always registers
    both files — see app/core/dependencies.py), but this stays defensive
    rather than letting a missing prompt file take down report assembly
    for an otherwise-successful analysis.
    """

    def _version(prompt_id: str) -> str | None:
        try:
            template = prompt_registry.get(prompt_id)
        except PromptNotFoundError:
            return None
        return template.metadata.version if template.metadata else None

    return PromptVersions(
        reasoning_pass=_version("reasoning_pass_v1"),
        coaching=_version("coaching_v1"),
    )
