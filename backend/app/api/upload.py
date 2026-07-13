from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.audio.errors import AudioValidationError, AudioValidationReason
from app.audio.ingestors.http_upload import HttpUploadIngestor
from app.audio.models import AudioAsset
from app.audio.service import AudioService
from app.core.dependencies import get_audio_service

# Sprint 3.3 consolidated what was briefly two routes (/api/audio from
# Sprint 3.2, /api/upload requested in 3.3) into this one. The URL is
# named for the action a caller takes ("upload a file"), while the
# underlying domain package stays app/audio/ — that package models the
# Audio Service from ADR 002 (AudioAsset, AudioService, AudioIngestor),
# a concept broader than just this one HTTP route, so it keeps its own
# name even though the route in front of it is now /api/upload.
router = APIRouter(prefix="/api/upload", tags=["upload"])

_REASON_TO_STATUS: dict[AudioValidationReason, int] = {
    AudioValidationReason.UNSUPPORTED_FORMAT: 400,
    AudioValidationReason.EMPTY_FILE: 400,
    AudioValidationReason.FILE_TOO_LARGE: 413,
}


@router.post("", response_model=AudioAsset, status_code=201)
async def upload_audio(
    file: UploadFile = File(...),
    audio_service: AudioService = Depends(get_audio_service),
) -> AudioAsset:
    """
    Accepts one audio file (.wav, .mp3, .m4a, or .webm — a browser
    recording or a directly picked file, indistinguishable from here),
    validates its format and size, and stores it temporarily.

    Deliberately does not transcribe or otherwise process the audio (does
    not call Whisper or any other provider) here — POST /api/upload/{id}/transcribe
    (Sprint 3.4) does that as a separate, explicit step. This endpoint's
    only job is producing a stored AudioAsset that TranscriptionService
    can consume without this endpoint changing — see AudioService.ingest
    and the Storage Layer interfaces it depends on.

    `audio_service` is now injected (see app/core/dependencies.py) rather
    than built as a private module-level singleton here, as it was in
    Sprint 3.2/3.3 — moved so this route and the new /transcribe route
    share the exact same AudioService/RecordStore instances. Two separate
    singletons would mean an asset uploaded here couldn't be found by the
    transcribe endpoint.
    """
    ingestor = HttpUploadIngestor(file)
    raw = await ingestor.ingest()

    try:
        return await audio_service.ingest(raw)
    except AudioValidationError as exc:
        raise HTTPException(
            status_code=_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc


@router.get("/{asset_id}", response_model=AudioAsset)
def get_audio(
    asset_id: str,
    audio_service: AudioService = Depends(get_audio_service),
) -> AudioAsset:
    """
    Looks up a previously uploaded file's metadata. Not called by the
    frontend yet (the POST response already carries everything the UI
    needs) — included because it's part of ADR 002's designed flow and
    useful for verifying an upload landed correctly.
    """
    asset = audio_service.get(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No upload found with that id."},
        )
    return asset
