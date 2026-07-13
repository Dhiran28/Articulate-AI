from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.audio.errors import AudioValidationError, AudioValidationReason
from app.audio.ingestors.http_upload import HttpUploadIngestor
from app.audio.models import AudioAsset
from app.audio.service import AudioService
from app.core.config import get_settings
from app.storage.blob_store import LocalTempBlobStore
from app.storage.record_store import InMemoryRecordStore

# Sprint 3.3 consolidated what was briefly two routes (/api/audio from
# Sprint 3.2, /api/upload requested in 3.3) into this one. The URL is
# named for the action a caller takes ("upload a file"), while the
# underlying domain package stays app/audio/ — that package models the
# Audio Service from ADR 002 (AudioAsset, AudioService, AudioIngestor),
# a concept broader than just this one HTTP route, so it keeps its own
# name even though the route in front of it is now /api/upload.
router = APIRouter(prefix="/api/upload", tags=["upload"])

settings = get_settings()

# Module-level singletons, matching main.py's existing pattern of reading
# settings once at import time. This sprint's stores are process-local (a
# local temp directory, an in-memory dict), so there's nothing gained yet
# from FastAPI's per-request dependency injection — that will matter once
# a real database/blob store is introduced and connection lifecycle
# actually needs managing.
_blob_store = LocalTempBlobStore(Path(settings.upload_temp_dir))
_record_store = InMemoryRecordStore()
_audio_service = AudioService(_blob_store, _record_store, settings.max_upload_size_bytes)

_REASON_TO_STATUS: dict[AudioValidationReason, int] = {
    AudioValidationReason.UNSUPPORTED_FORMAT: 400,
    AudioValidationReason.EMPTY_FILE: 400,
    AudioValidationReason.FILE_TOO_LARGE: 413,
}


@router.post("", response_model=AudioAsset, status_code=201)
async def upload_audio(file: UploadFile = File(...)) -> AudioAsset:
    """
    Accepts one audio file (.wav, .mp3, .m4a, or .webm — a browser
    recording or a directly picked file, indistinguishable from here),
    validates its format and size, and stores it temporarily.

    Deliberately does not transcribe or otherwise process the audio (does
    not call Whisper or any other provider) — that's the Transcription
    Service designed in ADR 002, not yet built. This endpoint's only job
    is producing a stored AudioAsset that a future Transcription Service
    can consume without this endpoint changing — see AudioService.ingest
    and the Storage Layer interfaces it depends on.
    """
    ingestor = HttpUploadIngestor(file)
    raw = await ingestor.ingest()

    try:
        return await _audio_service.ingest(raw)
    except AudioValidationError as exc:
        raise HTTPException(
            status_code=_REASON_TO_STATUS[exc.reason],
            detail={"error": exc.reason.value, "message": exc.message},
        ) from exc


@router.get("/{asset_id}", response_model=AudioAsset)
def get_audio(asset_id: str) -> AudioAsset:
    """
    Looks up a previously uploaded file's metadata. Not called by the
    frontend yet (the POST response already carries everything the UI
    needs) — included because it's part of ADR 002's designed flow and
    useful for verifying an upload landed correctly.
    """
    asset = _audio_service.get(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No upload found with that id."},
        )
    return asset
