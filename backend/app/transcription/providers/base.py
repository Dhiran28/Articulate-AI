from pathlib import Path
from typing import Protocol

from ..models import RawTranscriptionResult


class TranscriptionProvider(Protocol):
    """
    Per ADR 002 §1: "a thing that turns audio bytes into a raw
    transcription result." This is the seam Sprint 3.4 was asked to
    design around — OpenAIWhisperProvider (this sprint) is the first
    implementation; LocalWhisperProvider, DeepgramProvider, and
    AssemblyAIProvider are future siblings that implement this same
    shape. Nothing above this interface (TranscriptionService, the
    /transcribe route) knows or cares which one is actually wired in —
    that's decided entirely by app.core.dependencies.get_transcription_provider.

    `content_type` is passed alongside the file path because not every
    provider can infer format from a file path alone (this sprint's
    OpenAIWhisperProvider doesn't need it — see that class — but a future
    provider might).
    """

    async def transcribe(self, audio_path: Path, content_type: str) -> RawTranscriptionResult: ...
