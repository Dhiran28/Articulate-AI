"""
SpeakingPaceModule (Sprint 4.3) — a deterministic Metric module.

Reuses Sprint 3.5's TranscriptMetadata directly wherever the arithmetic
allows it: words per minute and average pause duration are both plain
division over fields TranscriptMetadata already computed (word_count,
duration_seconds, total_pause_seconds, disfluencies.pauses) — nothing
here re-tokenizes the transcript or re-derives pause gaps from scratch.
Average sentence length and longest pause are the two things Sprint 3.5
didn't need for its own scope and this module computes itself: sentence
length from punctuation-delimited chunks of processed_transcript.text,
longest pause by scanning the per-segment pause_before_seconds Sprint
3.5 already attached to each segment.

Deterministic and side-effect-free: reads only the given transcript and
returns a MetricResult. Never mutates the transcript, never calls
another module, never touches storage, the network, or the filesystem,
never invokes an LLM.
"""

import re
from typing import Any

from app.transcript_processing.models import TranscriptProcessingResult

from ..errors import AnalysisErrorReason
from ..models import MetricResult, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ResultMetadata

_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]+")
_WORD_PATTERN = re.compile(r"[A-Za-z']+")


class SpeakingPaceModule:
    module_name = "speaking_pace"
    module_type = ModuleType.METRIC

    def __init__(self) -> None:
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": (
                "Words per minute, sentence length, and pause timing derived "
                "from already-processed transcript data."
            ),
        }

    async def analyze(self, transcript: TranscriptProcessingResult) -> ModuleResult:
        duration = transcript.metadata.duration_seconds

        if not duration or duration <= 0:
            # Words-per-minute is undefined without a positive duration.
            # A classified failure, not a ZeroDivisionError bubbling out
            # of this module (ADR 003 §7's METRIC_INPUT_INVALID reason
            # exists exactly for this case).
            return ModuleResult(
                metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
                status=ModuleStatus.FAILED,
                error=ModuleErrorDetail(
                    reason=AnalysisErrorReason.METRIC_INPUT_INVALID,
                    message="Speaking pace requires a known, positive transcript duration.",
                ),
            )

        words_per_minute = transcript.metadata.word_count / (duration / 60)
        average_sentence_length = self._average_sentence_length(transcript.processed_transcript.text)

        pause_count = transcript.metadata.disfluencies.pauses
        average_pause_duration = (
            transcript.metadata.total_pause_seconds / pause_count if pause_count else None
        )

        longest_pause = max(
            (
                segment.pause_before_seconds
                for segment in transcript.processed_transcript.segments
                if segment.pause_before_seconds is not None
            ),
            default=None,
        )

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            metric=MetricResult(
                value=round(words_per_minute, 1),
                unit="words_per_minute",
                details={
                    "average_sentence_length": average_sentence_length,
                    "average_pause_duration_seconds": (
                        round(average_pause_duration, 2) if average_pause_duration is not None else None
                    ),
                    "longest_pause_seconds": longest_pause,
                },
            ),
        )

    def _average_sentence_length(self, text: str) -> float | None:
        """
        Splits on sentence-ending punctuation and averages word count per
        resulting chunk. An approximation, not a linguistic parse: ASR
        punctuation is itself a model guess, and disfluent speech doesn't
        always land on clean sentence boundaries — good enough for a
        deterministic estimate, not a claim of grammatical accuracy.
        """
        chunks = [c for c in _SENTENCE_SPLIT_PATTERN.split(text) if c.strip()]
        if not chunks:
            return None

        lengths = [len(_WORD_PATTERN.findall(chunk)) for chunk in chunks]
        lengths = [length for length in lengths if length > 0]
        if not lengths:
            return None

        return round(sum(lengths) / len(lengths), 2)
