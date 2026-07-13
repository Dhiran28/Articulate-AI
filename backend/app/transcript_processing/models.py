from pydantic import BaseModel

from app.transcription.models import RawTranscriptionResult


class ProcessedSegment(BaseModel):
    """
    One timed chunk of the processed transcript. Deliberately minimal and
    provider-agnostic — this is the canonical shape ADR 002 assigns to
    the Transcript Processor's output, independent of which provider (or
    how many different provider shapes) fed into it.
    """

    start: float
    end: float
    text: str
    pause_before_seconds: float | None = None
    """Gap since the previous segment ended, in seconds — only set when
    that gap clears TranscriptProcessor's "noticeable pause" threshold.
    None for the first segment (nothing precedes it) or when the gap is
    just normal speech-to-speech latency."""


class ProcessedTranscript(BaseModel):
    """
    The transcript after processing — reconciled into the canonical
    segment shape above, but NOT cleaned. `text` is verbatim identical to
    RawTranscriptionResult.text: filler words, repeated words, false
    starts, and self-corrections are all still there. See
    TranscriptProcessor's module docstring for why.
    """

    text: str
    segments: list[ProcessedSegment]


class DisfluencyCounts(BaseModel):
    """
    Mechanically countable communication-behavior signals. Only signals
    detectable with real precision get a count here — see
    TranscriptMetadata.processing_notes for what's deliberately not
    counted, and why counting it would be dishonest rather than useful.
    """

    filler_words: int = 0
    repeated_words: int = 0
    pauses: int = 0


class TranscriptMetadata(BaseModel):
    provider: str
    model: str
    language: str | None = None
    duration_seconds: float | None = None
    word_count: int
    segment_count: int
    total_pause_seconds: float
    disfluencies: DisfluencyCounts
    processing_notes: list[str] = []


class TranscriptProcessingResult(BaseModel):
    """The three-part output Sprint 3.5 asks for: Raw Transcript, Processed Transcript, Metadata."""

    raw_transcript: RawTranscriptionResult
    processed_transcript: ProcessedTranscript
    metadata: TranscriptMetadata
