from app.audio.service import AudioService
from app.storage.blob_store import AudioBlobStore

from .errors import TranscriptionError, TranscriptionErrorReason
from .models import RawTranscriptionResult
from .providers.base import TranscriptionProvider


class TranscriptionService:
    """
    Owns the "send an already-uploaded asset to a transcription provider,
    return its raw result" responsibility ADR 002 assigns to the
    Transcription Service. Depends on AudioService (to look up the
    asset's metadata) and AudioBlobStore (to locate its bytes on disk)
    from the existing Storage Layer, plus an injected TranscriptionProvider
    — never a concrete provider SDK directly, so swapping providers never
    touches this class.

    Deliberately does not normalize the result into a canonical Transcript
    or run any analysis on it — those are the Transcript Processor and AI
    Analysis Layer, both still unbuilt per ADR 002. This service's job
    ends at "here is what the provider said," per Sprint 3.4's explicit
    "return raw transcript only."
    """

    def __init__(
        self,
        audio_service: AudioService,
        blob_store: AudioBlobStore,
        provider: TranscriptionProvider,
    ) -> None:
        self._audio_service = audio_service
        self._blob_store = blob_store
        self._provider = provider

    async def transcribe_asset(self, asset_id: str) -> RawTranscriptionResult:
        asset = self._audio_service.get(asset_id)
        if asset is None:
            raise TranscriptionError(
                TranscriptionErrorReason.ASSET_NOT_FOUND,
                "No upload found with that id.",
            )

        audio_path = self._blob_store.path_for(asset_id, asset.format)
        if not audio_path.exists():
            # Should only happen if the temp file was cleaned up out from
            # under a still-referenced record — there's no cleanup job
            # yet (see backend/app/storage/blob_store.py), but this stays
            # a distinct, named failure rather than an unhandled
            # FileNotFoundError if that ever changes.
            raise TranscriptionError(
                TranscriptionErrorReason.ASSET_NOT_FOUND,
                "The uploaded file could not be found.",
            )

        return await self._provider.transcribe(audio_path, asset.content_type)
