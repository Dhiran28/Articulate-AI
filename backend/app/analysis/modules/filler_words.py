"""
FillerWordModule (Sprint 4.3) — a deterministic Metric module.

Reuses Sprint 3.5's TranscriptMetadata.disfluencies.filler_words as a
cross-check (see tests/test_metric_modules.py), but computes its own
per-word, per-occurrence breakdown here, because that aggregate count
alone can't answer "which fillers, how often each, and where" — the
itemized detail this module is specifically asked to produce.

Deterministic and side-effect-free: reads only the given transcript and
returns a MetricResult. Never mutates the transcript, never calls
another module, never touches storage, the network, or the filesystem,
never invokes an LLM.
"""

import re
from collections import Counter
from typing import Any

from ..models import AnalysisContext, MetricResult, ModuleResult, ModuleStatus, ModuleType, ResultMetadata

# Mirrors app/transcript_processing/processor.py's own tokenization
# ("[A-Za-z']+", lowercased) so filler counts computed here are directly
# comparable to Sprint 3.5's aggregate disfluencies.filler_words when
# using the same default dictionary. Kept as this module's own constant
# rather than importing processor.py's private _WORD_PATTERN — that name
# is an implementation detail of TranscriptProcessor, not a published
# contract this module should depend on.
_WORD_PATTERN = re.compile(r"[A-Za-z']+")

# The same nine-word list app/transcript_processing/processor.py uses by
# default (see that module's _FILLER_WORDS) — kept in sync deliberately
# so this module's default output matches Sprint 3.5's aggregate count
# exactly (verified in tests). Callers who want a different vocabulary
# pass their own set to the constructor.
_DEFAULT_FILLER_WORDS = frozenset({"um", "umm", "uh", "uhh", "erm", "er", "hmm", "mm", "mhm"})


class FillerWordModule:
    """
    Counts and locates filler words in the processed transcript.

    `filler_words` is the configurable dictionary this module evaluates
    against (defaults to the same list Sprint 3.5 uses). `top_n`
    controls how many of the most frequent fillers are surfaced in
    `top_fillers` — the full breakdown is always in `occurrences`
    regardless of `top_n`.
    """

    module_name = "filler_words"
    module_type = ModuleType.METRIC

    def __init__(self, filler_words: frozenset[str] | set[str] | None = None, top_n: int = 5) -> None:
        self._filler_words = frozenset(w.lower() for w in (filler_words or _DEFAULT_FILLER_WORDS))
        self._top_n = top_n
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Counts and locates configured filler words in the processed transcript.",
            "dictionary_size": len(self._filler_words),
        }

    async def analyze(self, context: AnalysisContext) -> ModuleResult:
        # Sprint 4.5: analyze() now receives the wider AnalysisContext,
        # not a bare transcript. This module is a Metric module, so
        # context.metrics is always {} (nothing has run before it — see
        # ModuleRegistry's two-phase order) and reasoning_context is
        # unused here; only the transcript itself is relevant.
        transcript = context.transcript
        occurrences: list[dict[str, Any]] = []

        for index, segment in enumerate(transcript.processed_transcript.segments):
            for token in _WORD_PATTERN.findall(segment.text):
                lowered = token.lower()
                if lowered in self._filler_words:
                    occurrences.append(
                        {
                            "word": lowered,
                            "segment_index": index,
                            "start": segment.start,
                            "end": segment.end,
                        }
                    )

        total_count = len(occurrences)
        word_count = transcript.metadata.word_count
        frequency_per_100_words = (total_count / word_count * 100) if word_count else 0.0

        counts = Counter(o["word"] for o in occurrences)
        top_fillers = [{"word": word, "count": count} for word, count in counts.most_common(self._top_n)]

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            metric=MetricResult(
                value=total_count,
                unit="count",
                details={
                    "frequency_per_100_words": round(frequency_per_100_words, 2),
                    "top_fillers": top_fillers,
                    "occurrences": occurrences,
                    "dictionary": sorted(self._filler_words),
                },
            ),
        )
