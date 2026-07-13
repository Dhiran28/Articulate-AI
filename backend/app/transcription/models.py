from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    """One timed chunk of a transcript, as a provider reports it."""

    start: float
    end: float
    text: str


class RawTranscriptionResult(BaseModel):
    """
    A transcription provider's result, deliberately kept close to what
    that provider actually returns rather than reconciled into one
    canonical cross-provider shape.

    Per ADR 002 §1, normalizing across providers (Whisper's flat segment
    list vs. Deepgram's word-level, speaker-diarized JSON, etc.) is the
    Transcript Processor's job — a separate, not-yet-built stage. "Raw"
    here means "not that normalization," not "untyped" — this is still a
    clean, typed response; `provider` and `model` just make clear which
    provider/model produced it, since callers shouldn't assume every
    RawTranscriptionResult was shaped identically.
    """

    provider: str
    model: str
    text: str
    language: str | None = None
    duration_seconds: float | None = None
    segments: list[TranscriptSegment] = []
