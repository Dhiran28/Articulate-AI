from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_transcript_processor, get_transcription_service
from app.transcript_processing.models import TranscriptProcessingResult
from app.transcript_processing.processor import TranscriptProcessor
from app.transcription.errors import TranscriptionError, TranscriptionErrorReason
from app.transcription.service import TranscriptionService

router = APIRouter(prefix="/api/upload", tags=["transcription"])

_REASON_TO_STATUS: dict[TranscriptionErrorReason, int] = {
    TranscriptionErrorReason.ASSET_NOT_FOUND: 404,
    TranscriptionErrorReason.PROVIDER_MISCONFIGURED: 503,
    TranscriptionErrorReason.PROVIDER_ERROR: 502,
}


@router.post("/{asset_id}/transcribe", response_model=TranscriptProcessingResult)
async def transcribe_upload(
    asset_id: str,
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    processor: TranscriptProcessor = Depends(get_transcript_processor),
) -> TranscriptProcessingResult:
    """
    Sends a previously uploaded audio file (POST /api/upload) to the
    configured transcription provider (Sprint 3.4), then runs the result
    through the Transcript Processor (Sprint 3.5) and returns all three
    pieces: the untouched raw provider output, the processed transcript,
    and metadata about it.

    Chaining both stages behind one request, rather than adding a second
    endpoint, matches what actually happens conceptually: "transcribe
    this audio" now means "give me the full pipeline's output," and a
    processed transcript is meaningless without the transcription that
    produced it — there's no case where a caller wants one without the
    other yet.

    The provider itself is injected (get_transcription_provider) so Local
    Whisper, Deepgram, or AssemblyAI can replace OpenAI Whisper later
    without this route changing. The processor deliberately does not
    analyze, summarize, or clean the transcript — see
    app/transcript_processing/processor.py for why "processing" here
    never means stripping filler words, pauses, hesitation, repeated
    words, false starts, or self-corrections. Full analysis is the AI
    Analysis Layer designed in ADR 002, still not built.
    """
    try:
        raw = await transcription_service.transcribe_asset(asset_id)
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc

    return processor.process(raw)
