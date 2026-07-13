from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.audio.errors import AudioValidationError, AudioValidationReason
from app.audio.ingestors.http_upload import HttpUploadIngestor
from app.audio.models import AudioAsset
from app.audio.service import AudioService
from app.core.config import get_settings
from app.storage.blob_store import LocalTempBlobStore
from app.storage.record_store import InMemoryRecordStore

router = APIRouter(prefix="/api/audio", tags=["audio"])

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

    Deliberately does not transcribe or otherwise process the audio —
    that's the Transcription Service designed in ADR 002, not yet built.
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
    frontend yet (the POST response already carries everything this
    sprint's UI needs) — included because it's part of ADR 002's designed
    flow and useful for verifying an upload landed correctly.
    """
    asset = _audio_service.get(asset_id)
    if asset is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No upload found with that id."},
        )
    return asset
