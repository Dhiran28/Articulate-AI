from app.storage.blob_store import AudioBlobStore
from app.storage.record_store import RecordStore

from .errors import AudioValidationError, AudioValidationReason
from .ingestors.base import RawAudioUpload
from .models import AudioAsset
from .streaming import read_within_limit
from .validation import validate_format


class AudioService:
    """
    Owns the "accept, validate, store" responsibility ADR 002 assigns to
    the Audio Service. Nothing about transcription lives here, or
    anywhere in this sprint — that's the Transcription Service, still
    interface-only until its own sprint. Depends only on the Storage
    Layer's two interfaces, never on a concrete disk path or database, so
    swapping either later doesn't touch this class.
    """

    def __init__(self, blob_store: AudioBlobStore, record_store: RecordStore, max_size_bytes: int) -> None:
        self._blob_store = blob_store
        self._record_store = record_store
        self._max_size_bytes = max_size_bytes

    async def ingest(self, raw: RawAudioUpload) -> AudioAsset:
        # Format is checked before a single byte is read — an obviously
        # unsupported file shouldn't cost a full read to reject.
        audio_format = validate_format(raw.filename, raw.content_type)

        data = await read_within_limit(raw.read, self._max_size_bytes)

        if len(data) == 0:
            raise AudioValidationError(AudioValidationReason.EMPTY_FILE, "The uploaded file is empty.")

        asset = AudioAsset(
            original_filename=raw.filename,
            format=audio_format,
            content_type=raw.content_type or "application/octet-stream",
            size_bytes=len(data),
        )

        self._blob_store.save(asset.id, audio_format, data)
        self._record_store.create(asset)

        return asset

    def get(self, asset_id: str) -> AudioAsset | None:
        return self._record_store.get(asset_id)
