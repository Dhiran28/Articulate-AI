from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.transcript_processing.models import TranscriptProcessingResult

from .errors import AnalysisErrorReason


class ModuleType(str, Enum):
    """
    Which kind of judgment a module makes. Sprint 4.2 scopes this to
    exactly the two kinds a module's `analyze()` entry point can be
    called uniformly for today: METRIC (deterministic, no LLM) and
    REASONING (semantic judgment — no implementation exists yet, since
    this sprint explicitly excludes LLM code). A future module that
    blends both (e.g. ADR 003's Confidence Indicators) is still tagged
    REASONING here; the hybrid nature is a documentation nuance, not a
    distinct value this enum needs to carry.
    """

    METRIC = "metric"
    REASONING = "reasoning"


class ModuleStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"


class ResultMetadata(BaseModel):
    """
    Provenance describing *where a ModuleResult came from* — kept as its
    own schema, separate from the metric/reasoning/error payload it
    describes, per Sprint 4.2's requirement to keep results, errors, and
    metadata as distinct shapes rather than one loosely-typed bag.
    """

    module_name: str
    module_type: ModuleType
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    description: str | None = None


class MetricResult(BaseModel):
    """
    A Metric module's successful output. Deliberately generic — no real
    metric logic exists yet (Sprint 4.2 explicitly excludes scoring
    logic). `details` is an open bag for whatever a future module needs;
    `value`/`unit` are typed because "a number and what it's a number
    of" is the one shape every metric module will plausibly share (a
    words-per-minute figure, a count, a rate).
    """

    value: float | int | None = None
    unit: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ReasoningResult(BaseModel):
    """
    A Reasoning module's successful output. Deliberately generic — no
    LLM integration exists yet (Sprint 4.2 explicitly excludes it).
    Shaped differently from MetricResult on purpose: a reasoning
    judgment is a label/explanation/evidence, not a value/unit — the two
    schemas being visibly different is what "separate metric results
    from reasoning results" (Sprint 4.2 requirement 4) actually means.
    """

    label: str | None = None
    explanation: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ModuleErrorDetail(BaseModel):
    """
    Why a module's result is `failed` — its own schema, distinct from a
    successful metric/reasoning payload, so a caller can tell "this
    module has no opinion because it failed" apart from "this module's
    opinion happens to be empty" at the type level, not just by
    convention.
    """

    reason: AnalysisErrorReason
    message: str


class ModuleResult(BaseModel):
    """
    One module's independent result (ADR 003 §1/§7): every module's
    result carries `metadata` regardless of outcome, and exactly one of
    `metric` / `reasoning` / `error` depending on that module's type and
    whether it succeeded — enforced below, not just documented, so a
    malformed result is a validation error rather than a silent
    ambiguity a caller has to guess about.
    """

    metadata: ResultMetadata
    status: ModuleStatus
    metric: MetricResult | None = None
    reasoning: ReasoningResult | None = None
    error: ModuleErrorDetail | None = None

    @model_validator(mode="after")
    def _exactly_one_payload(self) -> "ModuleResult":
        if self.status is ModuleStatus.FAILED:
            if self.error is None or self.metric is not None or self.reasoning is not None:
                raise ValueError("A failed ModuleResult must carry `error` and nothing else.")
            return self

        # status is OK
        if self.error is not None:
            raise ValueError("An `ok` ModuleResult must not carry `error`.")

        if self.metadata.module_type is ModuleType.METRIC:
            if self.metric is None or self.reasoning is not None:
                raise ValueError("An `ok` METRIC ModuleResult must carry `metric` and nothing else.")
        else:  # REASONING
            if self.reasoning is None or self.metric is not None:
                raise ValueError("An `ok` REASONING ModuleResult must carry `reasoning` and nothing else.")

        return self


class AnalysisContext(BaseModel):
    """
    Sprint 4.5: what every module actually receives, widened from Sprint
    4.2's bare `TranscriptProcessingResult`. Three things, matching the
    sprint's explicit requirement:

      - `transcript`: unchanged from Sprint 4.2/4.3 — the verbatim,
        processed transcript.
      - `metrics`: every already-completed Metric module's ModuleResult,
        keyed by module_name. Populated by ModuleRegistry.execute()
        running every METRIC module first, then handing this dict to
        every non-metric module (see registry.py) — a reasoning module
        never calls a metric module itself; it's simply handed the
        finished results. Always `{}` for a Metric module (nothing has
        run before it).
      - `reasoning_context`: an open, currently-unused-by-default
        extensibility hook for whatever else a future caller might want
        to hand every module (e.g. speaker role, prior-session history)
        — the same "define the shape now, build the substance later"
        treatment Sprint 1 gave `app/models/` and Sprint 3's ADR 002
        gave the AI Analysis Layer itself.

    This is a genuine, disclosed breaking change to the Sprint 4.2
    `AnalysisModule` interface (`analyze(transcript)` becomes
    `analyze(context)`) — see docs/decisions/003-*.md's Sprint 4.5
    revision note for why, and app/analysis/README.md for the migration
    every Sprint 4.3 Metric module went through.
    """

    transcript: TranscriptProcessingResult
    metrics: dict[str, ModuleResult] = Field(default_factory=dict)
    reasoning_context: dict[str, Any] = Field(default_factory=dict)


class AnalysisReport(BaseModel):
    """
    The Communication Intelligence Engine's complete output (ADR 003
    §1): one ModuleResult per registered module, keyed by module_name,
    and nothing else — no ranking, no highlights, no coaching language.
    That synthesis is the Coaching Engine's job over this report as its
    own, separate input (ADR 003 §1/§2).
    """

    transcript_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modules: dict[str, ModuleResult] = Field(default_factory=dict)
