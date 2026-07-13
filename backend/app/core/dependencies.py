"""
FastAPI dependency providers.

Sprint 3.4 asked for the transcription provider to be wired in via
dependency injection specifically so OpenAI Whisper can later be swapped
for Local Whisper, Deepgram, or AssemblyAI without touching
TranscriptionService or the /transcribe route — only what
get_transcription_provider() returns needs to change.

The upload endpoints (app/api/upload.py) previously built their own
private, module-level singletons instead of going through this file. They
were moved here — not to change their behavior, but because the new
/transcribe endpoint needs to look up assets created via POST /api/upload,
which only works if both routes share the exact same AudioService /
RecordStore instances.

Sprint 3.5 added get_transcript_processor for the Transcript Processor
stage (app/transcript_processing/) that turns a RawTranscriptionResult
into a ProcessedTranscript + TranscriptMetadata — see that package's
processor.py for why "processing" here never means "cleaning."

Every dependency function that has its own dependencies (get_audio_service,
get_transcription_service) declares them as `Depends(...)` parameters,
rather than calling e.g. get_blob_store() directly in its body. That
distinction matters more than it looks: FastAPI's app.dependency_overrides
(used in tests to substitute a fake provider) only intercepts calls that
go through FastAPI's own dependency resolution. A plain Python function
call inside a function body bypasses it entirely. An earlier draft of
this file called get_transcription_provider() directly from
get_transcription_service()'s body, which worked fine at runtime but
silently made get_transcription_provider un-overridable in tests — caught
during this sprint's own verification (see the Sprint 3.4 explanation),
not by inspection. Chaining Depends() throughout is what makes the
override actually reach every level of the tree.
"""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.audio.service import AudioService
from app.core.config import get_settings
from app.storage.blob_store import AudioBlobStore, LocalTempBlobStore
from app.storage.record_store import InMemoryRecordStore, RecordStore
from app.transcription.providers.base import TranscriptionProvider
from app.transcription.providers.openai_whisper import OpenAIWhisperProvider
from app.transcription.service import TranscriptionService
from app.transcript_processing.processor import TranscriptProcessor


@lru_cache
def get_blob_store() -> AudioBlobStore:
    settings = get_settings()
    return LocalTempBlobStore(Path(settings.upload_temp_dir))


@lru_cache
def get_record_store() -> RecordStore:
    return InMemoryRecordStore()


def get_audio_service(
    blob_store: AudioBlobStore = Depends(get_blob_store),
    record_store: RecordStore = Depends(get_record_store),
) -> AudioService:
    # Not itself cached: constructing it is cheap (it just wraps the two
    # already-cached singletons above), and per-request construction is
    # what lets FastAPI substitute either singleton via
    # dependency_overrides at test time.
    settings = get_settings()
    return AudioService(blob_store, record_store, settings.max_upload_size_bytes)


@lru_cache
def get_transcription_provider() -> TranscriptionProvider:
    """
    The dependency-injection seam Sprint 3.4 asked for. This is the one
    place that decides which TranscriptionProvider backs the /transcribe
    endpoint today. Swapping OpenAI Whisper for Local Whisper, Deepgram,
    or AssemblyAI later means changing what this function constructs (or
    branching on a new config value, e.g. a TRANSCRIPTION_PROVIDER
    setting, once more than one is real) — TranscriptionService and the
    route stay exactly as they are.

    In tests, override this directly via
    `app.dependency_overrides[get_transcription_provider] = ...` to
    substitute a fake provider without a real API key or network access —
    see the Sprint 3.4 verification notes for a working example.
    """
    settings = get_settings()
    return OpenAIWhisperProvider(api_key=settings.openai_api_key, model=settings.whisper_model)


def get_transcription_service(
    audio_service: AudioService = Depends(get_audio_service),
    blob_store: AudioBlobStore = Depends(get_blob_store),
    provider: TranscriptionProvider = Depends(get_transcription_provider),
) -> TranscriptionService:
    return TranscriptionService(audio_service, blob_store, provider)


@lru_cache
def get_transcript_processor() -> TranscriptProcessor:
    # No sub-dependencies of its own (it's a pure function over whatever
    # RawTranscriptionResult it's given), so a plain cached singleton is
    # enough — there's no provider-style swapping to support here yet.
    return TranscriptProcessor()
