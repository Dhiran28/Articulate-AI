"""
HesitationModule (Sprint 4.3) — a deterministic Metric module.

Scoped to silent pauses only — gaps between segments that Sprint 3.5
already detects and records on each ProcessedSegment.pause_before_seconds.
Filled hesitation sounds ("um," "uh") are FillerWordModule's job, the
same boundary ADR 003 §2 draws between the two dimensions, kept here so
neither module double-counts the other's signal.

Reuses Sprint 3.5's output directly: every pause this module reports is
read off ProcessedSegment.pause_before_seconds, never recomputed from
raw timestamps, and this module's pause count is expected to equal
TranscriptMetadata.disfluencies.pauses exactly (verified in
tests/test_metric_modules.py).

Deterministic and side-effect-free: reads only the given transcript and
returns a MetricResult. Never mutates the transcript, never calls
another module, never touches storage, the network, or the filesystem,
never invokes an LLM.
"""

from typing import Any

from ..models import AnalysisContext, MetricResult, ModuleResult, ModuleStatus, ModuleType, ResultMetadata


class HesitationModule:
    """
    Reports where and how long the speaker paused.

    `long_pause_threshold_seconds` is a second, stricter threshold
    applied on top of Sprint 3.5's own 0.5s "noticeable pause" cutoff —
    a pause has to already be noticeable (per Sprint 3.5) before this
    module can classify it as "long."
    """

    module_name = "hesitations"
    module_type = ModuleType.METRIC

    def __init__(self, long_pause_threshold_seconds: float = 1.5) -> None:
        self._long_pause_threshold_seconds = long_pause_threshold_seconds
        self.metadata: dict[str, Any] = {
            "version": "0.1.0",
            "description": "Locates and characterizes silent pauses already detected by the Transcript Processor.",
            "long_pause_threshold_seconds": long_pause_threshold_seconds,
        }

    async def analyze(self, context: AnalysisContext) -> ModuleResult:
        transcript = context.transcript
        segments = transcript.processed_transcript.segments
        duration = transcript.metadata.duration_seconds

        markers: list[dict[str, Any]] = [
            {
                "segment_index": index,
                "start": segment.start,
                "pause_seconds": segment.pause_before_seconds,
            }
            for index, segment in enumerate(segments)
            if segment.pause_before_seconds is not None
        ]

        long_pauses = [m for m in markers if m["pause_seconds"] >= self._long_pause_threshold_seconds]
        distribution = self._distribution(markers, duration)

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            metric=MetricResult(
                value=len(markers),
                unit="count",
                details={
                    "total_pause_seconds": transcript.metadata.total_pause_seconds,
                    "long_pause_threshold_seconds": self._long_pause_threshold_seconds,
                    "long_pauses": long_pauses,
                    "markers": markers,
                    "distribution": distribution,
                },
            ),
        )

    def _distribution(self, markers: list[dict[str, Any]], duration: float | None) -> dict[str, int]:
        """
        Buckets each pause into the early/middle/late third of the
        transcript by when it occurred, relative to total duration. Pure
        timestamp bucketing — no judgment about *why* a pause happened,
        just where. Returns all-zero buckets if duration isn't known
        rather than guessing.
        """
        buckets = {"early": 0, "middle": 0, "late": 0}
        if not duration:
            return buckets

        third = duration / 3
        for marker in markers:
            start = marker["start"]
            if start < third:
                buckets["early"] += 1
            elif start < 2 * third:
                buckets["middle"] += 1
            else:
                buckets["late"] += 1

        return buckets
