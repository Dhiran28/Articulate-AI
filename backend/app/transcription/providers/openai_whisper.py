import logging
from pathlib import Path

from openai import AsyncOpenAI, OpenAIError

from ..errors import TranscriptionError, TranscriptionErrorReason
from ..models import RawTranscriptionResult, TranscriptSegment

logger = logging.getLogger(__name__)


class OpenAIWhisperProvider:
    """
    Calls OpenAI's hosted Whisper API (POST /v1/audio/transcriptions).
    One of several TranscriptionProvider implementations this design
    anticipates (see ADR 002 §1 and providers/base.py) — Local Whisper,
    Deepgram, and AssemblyAI are future siblings that implement the same
    interface without TranscriptionService or the /transcribe route
    changing.

    If no API key is configured, the client is never constructed and
    every call fails fast with a clear PROVIDER_MISCONFIGURED error,
    rather than letting the OpenAI SDK raise its own less-friendly
    authentication error partway through a request.
    """

    def __init__(self, api_key: str | None, model: str = "whisper-1") -> None:
        self._client = AsyncOpenAI(api_key=api_key) if api_key else None
        self._model = model

    async def transcribe(self, audio_path: Path, content_type: str) -> RawTranscriptionResult:
        # content_type is part of the TranscriptionProvider interface for
        # providers that need an explicit format hint, but this one
        # doesn't: the OpenAI SDK infers the audio format from the open
        # file handle's name, and LocalTempBlobStore already names stored
        # files with their real extension (e.g. "<id>.wav").
        del content_type

        if self._client is None:
            raise TranscriptionError(
                TranscriptionErrorReason.PROVIDER_MISCONFIGURED,
                "Transcription isn't configured on the server. Set OPENAI_API_KEY and try again.",
            )

        try:
            with audio_path.open("rb") as audio_file:
                response = await self._client.audio.transcriptions.create(
                    model=self._model,
                    file=audio_file,
                    response_format="verbose_json",
                )
        except OpenAIError as exc:
            logger.exception("OpenAI Whisper request failed for %s", audio_path)
            raise TranscriptionError(
                TranscriptionErrorReason.PROVIDER_ERROR,
                "The transcription provider couldn't process this audio. Please try again.",
            ) from exc

        segments = [
            TranscriptSegment(start=segment.start, end=segment.end, text=segment.text)
            for segment in (response.segments or [])
        ]

        return RawTranscriptionResult(
            provider="openai_whisper",
            model=self._model,
            text=response.text,
            language=getattr(response, "language", None),
            duration_seconds=getattr(response, "duration", None),
            segments=segments,
        )
