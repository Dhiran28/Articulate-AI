from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_transcription_service
from app.transcription.errors import TranscriptionError, TranscriptionErrorReason
from app.transcription.models import RawTranscriptionResult
from app.transcription.service import TranscriptionService

router = APIRouter(prefix="/api/upload", tags=["transcription"])

_REASON_TO_STATUS: dict[TranscriptionErrorReason, int] = {
    TranscriptionErrorReason.ASSET_NOT_FOUND: 404,
    TranscriptionErrorReason.PROVIDER_MISCONFIGURED: 503,
    TranscriptionErrorReason.PROVIDER_ERROR: 502,
}


@router.post("/{asset_id}/transcribe", response_model=RawTranscriptionResult)
async def transcribe_upload(
    asset_id: str,
    service: TranscriptionService = Depends(get_transcription_service),
) -> RawTranscriptionResult:
    """
    Sends a previously uploaded audio file (POST /api/upload) to the
    configured transcription provider and returns its raw transcript.

    Deliberately does not analyze, summarize, or otherwise process the
    transcript — that's the AI Analysis Layer designed in ADR 002, not
    built yet. This endpoint's only job is "send audio, receive
    transcript." The provider itself is injected
    (app.core.dependencies.get_transcription_provider) specifically so
    Local Whisper, Deepgram, or AssemblyAI can replace OpenAI Whisper
    later without this route, or TranscriptionService, changing.
    """
    try:
        return await service.transcribe_asset(asset_id)
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc
