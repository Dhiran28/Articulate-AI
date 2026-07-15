from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .errors import AnalysisErrorReason


class ModuleCategory(str, Enum):
    """
    Which kind of judgment a module makes (ADR 003 §1/§2). A convention
    for readability, dispatch, and error-reporting — not a constraint
    AnalysisModule or BatchedReasoningModule enforce structurally. A
    future module is free to be a metric-like reasoning module or
    anything in between; this enum just needs a value for it.
    """

    METRIC = "metric"
    REASONING = "reasoning"
    HYBRID = "hybrid"


class ModuleStatus(str, Enum):
    OK = "ok"
    FAILED = "failed"


class ModuleResult(BaseModel):
    """
    One module's independent result. Deliberately carries evidence, not
    advice: turning "filler words appeared at a moderate rate, here's
    where" into "here's what to do about it" is the Coaching Engine's
    job (ADR 003 §1/§2), not this model's. Nothing here should ever read
    like a recommendation.

    `data` holds whatever dimension-specific fields a given module
    produces (a words-per-minute number, a structure label, a hedge
    count...) as an open mapping rather than a fixed set of fields,
    because this scaffolding sprint (4.2) builds no real modules yet to
    shape it against — see registry.py. A future sprint building the
    real modules may tighten this into a discriminated union once actual
    per-module shapes exist to discriminate between; inventing that
    union now, before any module needs it, would be guessing.
    """

    module_name: str
    category: ModuleCategory
    status: ModuleStatus
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reason: AnalysisErrorReason | None = None
    message: str | None = None


class AnalysisReport(BaseModel):
    """
    The Communication Intelligence Engine's complete output (ADR 003
    §1): one ModuleResult per registered module, and nothing else —
    no ranking, no highlights, no coaching language. That synthesis is
    the Coaching Engine's job, operating on this report as its own,
    separate input.

    Keyed by module_name (not a list) so a caller — the future API layer
    or the Coaching Engine — can look up a specific module's result
    directly, without depending on MODULE_REGISTRY's iteration order.

    `transcript_id` is threaded in explicitly by whoever calls
    AnalysisEngine.analyze(), not read off TranscriptProcessingResult
    itself — that model (app/transcript_processing/models.py) has no id
    field of its own; the caller already holds the asset id it used to
    request transcription in the first place (see engine.py).
    """

    transcript_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modules: dict[str, ModuleResult] = Field(default_factory=dict)
