"""
Tests for TranscriptProcessor (Sprint 3.5).

See tests/README.md for how this file fits into the overall suite.

test_processed_text_is_byte_identical_to_raw, below, is the most
important test in this file: it's the permanent regression guard for
this component's entire reason for existing — preserve communication
behavior, never clean it away.
"""

from app.transcript_processing.processor import TranscriptProcessor
from app.transcription.models import RawTranscriptionResult, TranscriptSegment

RAW_TEXT = (
    "So, um, I I think the the plan is solid. "
    "We should— actually, let's not do that. "
    "It's on Tuesday, no wait, Wednesday, sorry."
)

DISFLUENT_RESULT = RawTranscriptionResult(
    provider="fake_whisper",
    model="fake-model",
    text=RAW_TEXT,
    language="en",
    duration_seconds=7.0,
    segments=[
        TranscriptSegment(start=0.0, end=2.0, text="So, um, I I think the the plan is solid."),
        TranscriptSegment(start=3.0, end=5.0, text="We should— actually, let's not do that."),
        TranscriptSegment(start=5.2, end=7.0, text="It's on Tuesday, no wait, Wednesday, sorry."),
    ],
)


class TestPreservation:
    def test_processed_text_is_byte_identical_to_raw(self) -> None:
        """
        The core invariant Sprint 3.5 exists to guarantee. The fixture
        above contains a filler word ("um"), repeated words ("I I",
        "the the"), a false start (the em-dash cutoff), and
        self-correction cues ("no wait", "sorry", "actually") —
        processing must not alter any of it.
        """
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.processed_transcript.text == result.raw_transcript.text
        assert result.processed_transcript.text == RAW_TEXT

    def test_false_start_marker_survives_processing(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert "We should—" in result.processed_transcript.text

    def test_self_correction_cues_survive_processing(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert "no wait" in result.processed_transcript.text
        assert "sorry" in result.processed_transcript.text


class TestDisfluencyMetadata:
    def test_counts_filler_words(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.metadata.disfluencies.filler_words == 1  # "um"

    def test_counts_repeated_words_within_a_segment(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.metadata.disfluencies.repeated_words == 2  # "I I", "the the"

    def test_does_not_count_a_repeat_spanning_a_segment_boundary(self) -> None:
        """
        Documents a known, deliberate limitation: two segments whose
        boundary happens to share a word are NOT counted as a repeat,
        because repeated-word detection is scoped per-segment (see
        TranscriptProcessor's docstring for why that tradeoff was made).
        """
        raw = RawTranscriptionResult(
            provider="fake",
            model="fake",
            text="the end. the beginning.",
            segments=[
                TranscriptSegment(start=0.0, end=1.0, text="the end."),
                TranscriptSegment(start=1.0, end=2.0, text="the beginning."),
            ],
        )
        result = TranscriptProcessor().process(raw)
        assert result.metadata.disfluencies.repeated_words == 0

    def test_detects_a_pause_above_the_threshold(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.metadata.disfluencies.pauses == 1
        assert result.metadata.total_pause_seconds == 1.0
        assert result.processed_transcript.segments[1].pause_before_seconds == 1.0

    def test_does_not_flag_a_gap_below_the_pause_threshold(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        # Gap between segment 2 (ends 5.0) and segment 3 (starts 5.2) is
        # 0.2s — below the 0.5s threshold, so not flagged as a pause.
        assert result.processed_transcript.segments[2].pause_before_seconds is None

    def test_first_segment_has_no_pause_before_it(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.processed_transcript.segments[0].pause_before_seconds is None

    def test_metadata_passes_through_provider_fields(self) -> None:
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        assert result.metadata.provider == "fake_whisper"
        assert result.metadata.model == "fake-model"
        assert result.metadata.language == "en"
        assert result.metadata.duration_seconds == 7.0
        assert result.metadata.segment_count == 3

    def test_false_starts_and_self_corrections_are_disclosed_as_uncounted(self) -> None:
        """
        Sprint 3.5 deliberately does not attempt to count false starts or
        self-corrections (see TranscriptProcessor's docstring) — but that
        limitation must be actively disclosed, not silently absent. This
        guards against a future edit accidentally deleting that
        disclosure from processing_notes.
        """
        result = TranscriptProcessor().process(DISFLUENT_RESULT)
        notes = " ".join(result.metadata.processing_notes).lower()
        assert "false start" in notes
        assert "self-correction" in notes


class TestEdgeCases:
    def test_empty_transcript_does_not_crash(self) -> None:
        raw = RawTranscriptionResult(
            provider="fake",
            model="fake",
            text="",
            language=None,
            duration_seconds=0.0,
            segments=[],
        )
        result = TranscriptProcessor().process(raw)
        assert result.processed_transcript.text == ""
        assert result.processed_transcript.segments == []
        assert result.metadata.word_count == 0
        assert result.metadata.disfluencies.filler_words == 0
        assert result.metadata.disfluencies.pauses == 0

    def test_single_segment_transcript(self) -> None:
        raw = RawTranscriptionResult(
            provider="fake",
            model="fake",
            text="hello world",
            segments=[TranscriptSegment(start=0.0, end=1.0, text="hello world")],
        )
        result = TranscriptProcessor().process(raw)
        assert len(result.processed_transcript.segments) == 1
        assert result.processed_transcript.segments[0].pause_before_seconds is None
