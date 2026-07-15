"""
Tests for the four deterministic Metric modules (Sprint 4.3):
FillerWordModule, HesitationModule, RepetitionModule, SpeakingPaceModule.

See tests/README.md for how this file fits into the overall suite, and
backend/app/analysis/README.md for the modules' own documentation.

Shared fixture: one deliberately constructed transcript with known
fillers, an immediate word repeat, several repeated phrases, and pauses
of varying length (one short, two just past Sprint 3.5's 0.5s threshold,
one past this sprint's 1.5s "long pause" threshold) — built once so every
module's tests exercise the same, hand-checked scenario. Where a value
is simple enough to hand-verify (filler count, pause count, longest
pause, words-per-minute), tests assert the exact expected number. Where
a value is a derived aggregate (RepetitionModule's headline count), tests
assert internal consistency against the module's own itemized detail
instead of a hand-computed literal — a more robust check than trusting
manual arithmetic over eight overlapping n-gram matches.
"""

import pytest

from app.analysis.errors import AnalysisErrorReason
from app.analysis.models import ModuleStatus, ModuleType
from app.analysis.modules.base import AnalysisModule
from app.analysis.modules.filler_words import FillerWordModule
from app.analysis.modules.hesitations import HesitationModule
from app.analysis.modules.repetitions import RepetitionModule
from app.analysis.modules.speaking_pace import SpeakingPaceModule
from app.transcription.models import RawTranscriptionResult, TranscriptSegment
from app.transcript_processing.processor import TranscriptProcessor

_SEGMENTS = [
    ("So, um, I think the the plan is solid.", 0.0, 2.0),
    ("We should move forward with the plan.", 2.7, 4.0),  # gap 0.7 — pause, not long
    ("Right.", 4.8, 5.0),  # gap 0.8 — pause, not long
    ("The plan is solid, I think.", 7.0, 8.5),  # gap 2.0 — pause, long
    ("Let's move forward.", 8.7, 9.0),  # gap 0.2 — below threshold, no pause
]


def _transcript():
    text = " ".join(t for t, _, _ in _SEGMENTS)
    raw = RawTranscriptionResult(
        provider="fake",
        model="fake",
        text=text,
        duration_seconds=9.0,
        segments=[TranscriptSegment(start=s, end=e, text=t) for t, s, e in _SEGMENTS],
    )
    return TranscriptProcessor().process(raw)


@pytest.fixture
def transcript():
    return _transcript()


class TestInterfaceConformance:
    """Each module must satisfy Sprint 4.2's AnalysisModule Protocol."""

    @pytest.mark.parametrize(
        "module",
        [FillerWordModule(), HesitationModule(), RepetitionModule(), SpeakingPaceModule()],
        ids=["filler_words", "hesitations", "repetitions", "speaking_pace"],
    )
    def test_satisfies_analysis_module_protocol(self, module) -> None:
        assert isinstance(module, AnalysisModule)
        assert module.module_type == ModuleType.METRIC
        assert isinstance(module.metadata, dict)


class TestDeterminism:
    """Same input, same output, every time — no hidden state, no randomness."""

    @pytest.mark.parametrize(
        "module_factory",
        [FillerWordModule, HesitationModule, RepetitionModule, SpeakingPaceModule],
        ids=["filler_words", "hesitations", "repetitions", "speaking_pace"],
    )
    async def test_running_twice_produces_identical_results(self, module_factory, transcript) -> None:
        module = module_factory()
        first = await module.analyze(transcript)
        second = await module.analyze(transcript)
        # Compare everything except `generated_at`, which is expected to
        # differ between calls (it's a timestamp, not an analysis
        # value) — the analytical content itself must be identical.
        assert first.status == second.status
        assert first.metric == second.metric
        assert first.reasoning == second.reasoning
        assert first.error == second.error

    async def test_does_not_mutate_the_transcript(self, transcript) -> None:
        before = transcript.model_copy(deep=True)
        for module in (FillerWordModule(), HesitationModule(), RepetitionModule(), SpeakingPaceModule()):
            await module.analyze(transcript)
        assert transcript == before


class TestFillerWordModule:
    async def test_total_matches_sprint_3_5s_default_dictionary_count(self, transcript) -> None:
        result = await FillerWordModule().analyze(transcript)
        assert result.status == ModuleStatus.OK
        # Same default dictionary as TranscriptProcessor -> same total.
        assert result.metric.value == transcript.metadata.disfluencies.filler_words
        assert result.metric.value == 1  # exactly one "um" in the fixture

    async def test_occurrences_are_located(self, transcript) -> None:
        result = await FillerWordModule().analyze(transcript)
        occurrences = result.metric.details["occurrences"]
        assert len(occurrences) == 1
        assert occurrences[0]["word"] == "um"
        assert occurrences[0]["segment_index"] == 0

    async def test_top_fillers_reflects_counts(self, transcript) -> None:
        result = await FillerWordModule().analyze(transcript)
        top = result.metric.details["top_fillers"]
        assert top == [{"word": "um", "count": 1}]

    async def test_frequency_is_relative_to_word_count(self, transcript) -> None:
        result = await FillerWordModule().analyze(transcript)
        expected = round(1 / transcript.metadata.word_count * 100, 2)
        assert result.metric.details["frequency_per_100_words"] == expected

    async def test_configurable_dictionary_changes_the_result(self, transcript) -> None:
        # "think" isn't a filler by default; a custom dictionary can say
        # otherwise, and the module must honor it rather than the fixed
        # Sprint 3.5 list.
        module = FillerWordModule(filler_words={"think"})
        result = await module.analyze(transcript)
        assert result.metric.value == 2  # "I think" appears twice in the fixture

    async def test_empty_transcript_returns_zero_not_a_failure(self) -> None:
        empty = TranscriptProcessor().process(
            RawTranscriptionResult(provider="fake", model="fake", text="", segments=[])
        )
        result = await FillerWordModule().analyze(empty)
        assert result.status == ModuleStatus.OK
        assert result.metric.value == 0
        assert result.metric.details["occurrences"] == []


class TestHesitationModule:
    async def test_pause_count_matches_sprint_3_5(self, transcript) -> None:
        result = await HesitationModule().analyze(transcript)
        assert result.status == ModuleStatus.OK
        assert result.metric.value == transcript.metadata.disfluencies.pauses
        assert result.metric.value == 3

    async def test_total_pause_seconds_matches_sprint_3_5(self, transcript) -> None:
        result = await HesitationModule().analyze(transcript)
        assert result.metric.details["total_pause_seconds"] == transcript.metadata.total_pause_seconds

    async def test_long_pauses_use_the_stricter_threshold(self, transcript) -> None:
        result = await HesitationModule(long_pause_threshold_seconds=1.5).analyze(transcript)
        long_pauses = result.metric.details["long_pauses"]
        # Only the 2.0s gap clears 1.5s; the 0.7s and 0.8s gaps don't.
        assert len(long_pauses) == 1
        assert long_pauses[0]["pause_seconds"] == 2.0

    async def test_distribution_buckets_by_position_in_the_transcript(self, transcript) -> None:
        result = await HesitationModule().analyze(transcript)
        assert result.metric.details["distribution"] == {"early": 1, "middle": 1, "late": 1}

    async def test_filler_words_are_not_counted_as_hesitations(self, transcript) -> None:
        # "um" in segment 0 is a filled hesitation, not a silent pause —
        # it must not appear in this module's markers.
        result = await HesitationModule().analyze(transcript)
        segment_indices = [m["segment_index"] for m in result.metric.details["markers"]]
        assert 0 not in segment_indices

    async def test_empty_transcript_returns_zero_not_a_failure(self) -> None:
        empty = TranscriptProcessor().process(
            RawTranscriptionResult(provider="fake", model="fake", text="", segments=[])
        )
        result = await HesitationModule().analyze(empty)
        assert result.status == ModuleStatus.OK
        assert result.metric.value == 0
        assert result.metric.details["distribution"] == {"early": 0, "middle": 0, "late": 0}


class TestRepetitionModule:
    async def test_immediate_repetitions_match_sprint_3_5(self, transcript) -> None:
        result = await RepetitionModule().analyze(transcript)
        assert result.status == ModuleStatus.OK
        immediate = result.metric.details["immediate_repetitions"]
        assert len(immediate) == transcript.metadata.disfluencies.repeated_words
        assert immediate == [{"word": "the", "segment_index": 0, "start": 0.0}]

    async def test_repeated_words_tally(self, transcript) -> None:
        result = await RepetitionModule().analyze(transcript)
        assert result.metric.details["repeated_words"] == {"the": 1}

    async def test_repeated_phrases_are_detected_across_segments(self, transcript) -> None:
        # "the plan" (segments 1 and 3) and "i think" (segments 0 and 3)
        # both repeat across segment boundaries — phrase repetition is
        # deliberately not segment-scoped, unlike immediate repetition.
        result = await RepetitionModule().analyze(transcript)
        phrases = {p["phrase"]: p["count"] for p in result.metric.details["repeated_phrases"]}
        assert phrases["the plan"] == 3
        assert phrases["i think"] == 2
        assert phrases["the plan is solid"] == 2  # a length-4 repeated phrase

    async def test_headline_count_is_internally_consistent(self, transcript) -> None:
        # Rather than hand-computing the aggregate across eight
        # overlapping n-gram matches, verify the module's own stated
        # formula against its own itemized detail.
        result = await RepetitionModule().analyze(transcript)
        details = result.metric.details
        expected = len(details["immediate_repetitions"]) + sum(
            p["count"] - 1 for p in details["repeated_phrases"]
        )
        assert result.metric.value == expected

    async def test_configurable_phrase_lengths(self, transcript) -> None:
        module = RepetitionModule(phrase_lengths=(2,))
        result = await module.analyze(transcript)
        lengths = {p["length"] for p in result.metric.details["repeated_phrases"]}
        assert lengths == {2}

    async def test_empty_transcript_returns_zero_not_a_failure(self) -> None:
        empty = TranscriptProcessor().process(
            RawTranscriptionResult(provider="fake", model="fake", text="", segments=[])
        )
        result = await RepetitionModule().analyze(empty)
        assert result.status == ModuleStatus.OK
        assert result.metric.value == 0


class TestSpeakingPaceModule:
    async def test_words_per_minute_from_metadata(self, transcript) -> None:
        result = await SpeakingPaceModule().analyze(transcript)
        assert result.status == ModuleStatus.OK
        expected = round(transcript.metadata.word_count / (transcript.metadata.duration_seconds / 60), 1)
        assert result.metric.value == expected
        assert result.metric.unit == "words_per_minute"

    async def test_average_sentence_length(self, transcript) -> None:
        result = await SpeakingPaceModule().analyze(transcript)
        # 5 sentences, 26 words total (see module fixture) -> 5.2 avg.
        assert result.metric.details["average_sentence_length"] == 5.2

    async def test_average_pause_duration_from_metadata(self, transcript) -> None:
        result = await SpeakingPaceModule().analyze(transcript)
        expected = round(
            transcript.metadata.total_pause_seconds / transcript.metadata.disfluencies.pauses, 2
        )
        assert result.metric.details["average_pause_duration_seconds"] == expected

    async def test_longest_pause(self, transcript) -> None:
        result = await SpeakingPaceModule().analyze(transcript)
        assert result.metric.details["longest_pause_seconds"] == 2.0

    async def test_missing_duration_is_a_classified_failure_not_a_crash(self) -> None:
        raw = RawTranscriptionResult(
            provider="fake",
            model="fake",
            text="Hello there, this is a test.",
            duration_seconds=None,
            segments=[TranscriptSegment(start=0.0, end=1.0, text="Hello there, this is a test.")],
        )
        transcript_no_duration = TranscriptProcessor().process(raw)

        result = await SpeakingPaceModule().analyze(transcript_no_duration)

        assert result.status == ModuleStatus.FAILED
        assert result.error.reason == AnalysisErrorReason.METRIC_INPUT_INVALID

    async def test_no_pauses_gives_none_not_a_crash(self) -> None:
        raw = RawTranscriptionResult(
            provider="fake",
            model="fake",
            text="Hello there.",
            duration_seconds=2.0,
            segments=[TranscriptSegment(start=0.0, end=2.0, text="Hello there.")],
        )
        transcript_no_pauses = TranscriptProcessor().process(raw)

        result = await SpeakingPaceModule().analyze(transcript_no_pauses)

        assert result.status == ModuleStatus.OK
        assert result.metric.details["average_pause_duration_seconds"] is None
        assert result.metric.details["longest_pause_seconds"] is None
