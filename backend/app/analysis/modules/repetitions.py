"""
RepetitionModule (Sprint 4.3) — a deterministic Metric module.

Two distinct kinds of repetition, deliberately scoped differently:

  - Immediate repetitions ("the the," "I I"): adjacent identical word
    tokens *within a single segment*. Recomputes Sprint 3.5's own
    adjacent-token comparison (app/transcript_processing/processor.py)
    rather than reusing its bare count, because this module needs the
    itemized instances (which word, where) that aggregate count alone
    can't provide — the total is expected to equal
    TranscriptMetadata.disfluencies.repeated_words exactly (verified in
    tests/test_metric_modules.py). Kept segment-scoped for the same
    reason Sprint 3.5 chose that scope: two unrelated sentences that
    happen to share a boundary word shouldn't count as a repeat.

  - Repeated phrases ("the plan is" appearing twice): exact n-gram
    matches anywhere in the transcript, deliberately NOT scoped to a
    single segment — repeating a whole phrase across two different
    segments is a real, meaningful signal, unlike a single boundary word
    repeating by coincidence.

This is exact string matching, not paraphrase detection: restating the
same point in different words is a semantic phenomenon this module
cannot honestly measure — that belongs to a future reasoning module, not
this one (the same principle Sprint 3.5 applied to false starts and
self-corrections).

Deterministic and side-effect-free: reads only the given transcript and
returns a MetricResult. Never mutates the transcript, never calls
another module, never touches storage, the network, or the filesystem,
never invokes an LLM.
"""

import re
from collections import Counter
from typing import Any

from app.transcript_processing.models import TranscriptProcessingResult

from ..models import AnalysisContext, MetricResult, ModuleResult, ModuleStatus, ModuleType, ResultMetadata

_WORD_PATTERN = re.compile(r"[A-Za-z']+")
"""Mirrors app/transcript_processing/processor.py's own tokenization —
see filler_words.py for why this is kept as a local constant rather than
importing that module's private pattern."""


class RepetitionModule:
    """
    `phrase_lengths` configures which n-gram sizes are checked for
    repeated phrases (default: 2, 3, and 4-word sequences). A repeated
    long phrase will also register its shorter overlapping sub-phrases
    as repeats — this module doesn't deduplicate to "only the longest
    match," to keep the detection logic simple and auditable; a caller
    that wants deduplicated output can post-process `repeated_phrases`.
    """

    module_name = "repetitions"
    module_type = ModuleType.METRIC

    def __init__(self, phrase_lengths: tuple[int, ...] = (2, 3, 4)) -> None:
        self._phrase_lengths = phrase_lengths
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Detects immediate word repeats and exact repeated phrases.",
            "phrase_lengths": list(phrase_lengths),
        }

    async def analyze(self, context: AnalysisContext) -> ModuleResult:
        transcript = context.transcript
        immediate_repetitions = self._immediate_repetitions(transcript)
        repeated_words = self._tally(immediate_repetitions)
        repeated_phrases = self._repeated_phrases(transcript)

        # A simple additive headline count — immediate-repetition
        # instances plus each repeated phrase's occurrences beyond the
        # first. Not a deduplicated canonical total (an immediate
        # repetition can also form part of a repeated phrase and get
        # reflected in both figures); `details` below is the source of
        # truth for anything more precise than this one summary number.
        repetition_count = len(immediate_repetitions) + sum(p["count"] - 1 for p in repeated_phrases)

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            metric=MetricResult(
                value=repetition_count,
                unit="count",
                details={
                    "immediate_repetitions": immediate_repetitions,
                    "repeated_words": repeated_words,
                    "repeated_phrases": repeated_phrases,
                },
            ),
        )

    def _immediate_repetitions(self, transcript: TranscriptProcessingResult) -> list[dict[str, Any]]:
        instances: list[dict[str, Any]] = []
        for index, segment in enumerate(transcript.processed_transcript.segments):
            tokens = [t.lower() for t in _WORD_PATTERN.findall(segment.text)]
            for i in range(1, len(tokens)):
                if tokens[i] == tokens[i - 1]:
                    instances.append({"word": tokens[i], "segment_index": index, "start": segment.start})
        return instances

    def _tally(self, immediate_repetitions: list[dict[str, Any]]) -> dict[str, int]:
        return dict(Counter(item["word"] for item in immediate_repetitions))

    def _repeated_phrases(self, transcript: TranscriptProcessingResult) -> list[dict[str, Any]]:
        tokens = [t.lower() for t in _WORD_PATTERN.findall(transcript.processed_transcript.text)]

        phrase_counts: Counter[str] = Counter()
        for n in self._phrase_lengths:
            for i in range(len(tokens) - n + 1):
                phrase = " ".join(tokens[i : i + n])
                phrase_counts[phrase] += 1

        return [
            {"phrase": phrase, "count": count, "length": len(phrase.split())}
            for phrase, count in phrase_counts.items()
            if count > 1
        ]
