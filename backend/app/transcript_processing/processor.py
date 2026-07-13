import re

from app.transcription.models import RawTranscriptionResult

from .models import (
    DisfluencyCounts,
    ProcessedSegment,
    ProcessedTranscript,
    TranscriptMetadata,
    TranscriptProcessingResult,
)

_WORD_PATTERN = re.compile(r"[A-Za-z']+")

_FILLER_WORDS = {"um", "umm", "uh", "uhh", "erm", "er", "hmm", "mm", "mhm"}

_PAUSE_THRESHOLD_SECONDS = 0.5
"""Gap between two segments below this is ordinary speech-to-speech
latency, not a "pause" worth surfacing. A reasonable, commonly-used floor
for a perceptible pause — adjustable if a future sprint finds it too
sensitive or not sensitive enough."""


class TranscriptProcessor:
    """
    Turns a provider's RawTranscriptionResult into a ProcessedTranscript
    plus TranscriptMetadata, without altering a single word of what was
    actually said.

    Why "processing" isn't "cleaning": most transcript pipelines exist to
    make a transcript easier to *read* — stripping "um"s, collapsing
    repeated words, smoothing over false starts. That's the wrong goal
    here. Articulate AI coaches how someone structures and delivers an
    argument, not their grammar — a filler word, a hesitation, a false
    start, or a self-correction isn't noise to this product, it's exactly
    the behavior a communication coach needs to see. So this processor's
    only jobs are:

      1. Reconcile whatever shape the provider returned into one
         canonical segment structure (today a near-1:1 mapping, since
         there's only one provider — see the note at the bottom of this
         docstring for where a second provider's reconciliation logic
         would go).
      2. Compute *additional* signal about the transcript (counts, pause
         locations) without ever rewriting its text.

    `processed_transcript.text` is therefore always exactly
    `raw_transcript.text` — same words, same order, nothing removed.

    What gets counted vs. what's merely preserved: filler words, repeated
    words, and pauses are mechanically detectable with real precision (a
    fixed word list; adjacent-token matching within a segment; a
    timestamp gap), so they get an actual count in
    TranscriptMetadata.disfluencies. False starts and self-corrections
    are just as thoroughly preserved — nothing in this class ever
    inspects the *content* of a word to decide whether to drop it — but
    they are NOT independently counted. Reliably detecting a false start
    or a self-correction is a semantic judgment (was this thought
    abandoned and restarted?), not a pattern match, and a regex that
    pretends otherwise would produce a confident-looking number with no
    real basis behind it. TranscriptMetadata.processing_notes says this
    explicitly. That kind of detection is a reasonable job for a future
    AI Analysis Layer pass with actual language understanding — not this
    processor.

    ADR 002 sketched per-provider normalizers/ for this stage, for
    reconciling genuinely different provider shapes (e.g. Deepgram's
    word-level, speaker-diarized JSON) into this same canonical shape.
    With only one real provider today, that indirection would be
    speculative — the mapping lives directly in process() below and
    should move into normalizers/ exactly when a second, differently
    -shaped provider arrives, not before.
    """

    def process(self, raw: RawTranscriptionResult) -> TranscriptProcessingResult:
        segments = self._to_processed_segments(raw)
        disfluencies, total_pause_seconds = self._analyze(raw, segments)

        metadata = TranscriptMetadata(
            provider=raw.provider,
            model=raw.model,
            language=raw.language,
            duration_seconds=raw.duration_seconds,
            word_count=len(_WORD_PATTERN.findall(raw.text)),
            segment_count=len(raw.segments),
            total_pause_seconds=total_pause_seconds,
            disfluencies=disfluencies,
            processing_notes=[
                "Filler word count is a lexical match against a fixed word "
                "list (um, uh, hmm, ...) and can miss or over-count "
                "context-dependent fillers ('like', 'so', 'you know') that "
                "are also legitimate words in other contexts.",
                "Repeated-word count compares adjacent word tokens within "
                "each provider segment, not across the whole transcript — "
                "this avoids miscounting two unrelated sentences that "
                "happen to share a boundary word, at the cost of possibly "
                "missing a repeat that spans exactly a segment cut.",
                "False starts and self-corrections are preserved verbatim "
                "in processed_transcript.text (nothing is removed or "
                "rewritten) but are not independently counted here — "
                "reliably detecting them requires language understanding "
                "beyond this processor's scope, and is a good candidate "
                "for a future AI Analysis Layer pass instead of a "
                "heuristic pretending to be one.",
            ],
        )

        return TranscriptProcessingResult(
            raw_transcript=raw,
            processed_transcript=ProcessedTranscript(text=raw.text, segments=segments),
            metadata=metadata,
        )

    def _to_processed_segments(self, raw: RawTranscriptionResult) -> list[ProcessedSegment]:
        segments: list[ProcessedSegment] = []
        previous_end: float | None = None

        for segment in raw.segments:
            pause_before = None
            if previous_end is not None:
                gap = segment.start - previous_end
                if gap >= _PAUSE_THRESHOLD_SECONDS:
                    pause_before = gap

            segments.append(
                ProcessedSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    pause_before_seconds=pause_before,
                )
            )
            previous_end = segment.end

        return segments

    def _analyze(
        self, raw: RawTranscriptionResult, segments: list[ProcessedSegment]
    ) -> tuple[DisfluencyCounts, float]:
        all_tokens = [token.lower() for token in _WORD_PATTERN.findall(raw.text)]
        filler_count = sum(1 for token in all_tokens if token in _FILLER_WORDS)

        repeated_count = 0
        for segment in raw.segments:
            segment_tokens = [token.lower() for token in _WORD_PATTERN.findall(segment.text)]
            repeated_count += sum(
                1
                for i in range(1, len(segment_tokens))
                if segment_tokens[i] == segment_tokens[i - 1]
            )

        pause_segments = [s for s in segments if s.pause_before_seconds is not None]
        total_pause_seconds = sum(s.pause_before_seconds for s in pause_segments)

        return (
            DisfluencyCounts(
                filler_words=filler_count,
                repeated_words=repeated_count,
                pauses=len(pause_segments),
            ),
            total_pause_seconds,
        )
