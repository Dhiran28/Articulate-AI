from typing import Any, Protocol, runtime_checkable

from ..models import AnalysisContext, ModuleResult, ModuleType


@runtime_checkable
class AnalysisModule(Protocol):
    """
    The one required module contract every analysis module implements —
    Metric (Sprint 4.3) and Reasoning (Sprint 4.5) alike:

      - `module_name`: a unique identifier (see ModuleRegistry —
        duplicate names are rejected at registration).
      - `module_type`: METRIC or REASONING (models.ModuleType) — a
        convention for dispatch/reporting, not a constraint this
        Protocol enforces structurally.
      - `metadata`: free-form static info the module exposes about
        itself (e.g. a version or short description) — distinct from
        ResultMetadata (models.py), which is provenance attached to a
        *result*, not the module's own self-description.
      - `analyze()`: given an AnalysisContext, return this module's
        ModuleResult.

    `@runtime_checkable` lets ModuleRegistry and AnalysisEngine verify a
    registered object actually satisfies this shape with a plain
    isinstance() check.

    Sprint 4.5 change (a genuine, disclosed breaking change from Sprint
    4.2): `analyze()` used to take a bare TranscriptProcessingResult.
    It now takes an AnalysisContext, which carries the transcript plus
    two more things Sprint 4.5 requires every module receive: `metrics`
    (every already-completed Metric module's ModuleResult, so a
    Reasoning module can use deterministic signal as context without
    calling another module itself — see ModuleRegistry.execute's
    two-phase order) and `reasoning_context` (an open extensibility
    hook, unused by default). See docs/decisions/003-*.md's Sprint 4.5
    revision note for the full reasoning behind this change, and
    app/analysis/README.md for what every Sprint 4.3 module had to
    change to keep working.

    A note on where ADR 003's "reasoning modules should not
    independently call the LLM by default" requirement goes from here:
    Sprint 4.5's six reasoning modules each still call the shared
    LLMReasoner once per module — genuinely not batched into one
    combined request. This is a disclosed, deliberate scope decision,
    not an oversight: batching (a ReasoningPass coordinating multiple
    modules' analyze() calls into one shared LLM request) is real,
    separate work this sprint didn't build. See
    app/analysis/reasoning_pass/README.md and this sprint's own
    completion notes for the explicit flag.
    """

    module_name: str
    module_type: ModuleType
    metadata: dict[str, Any]

    async def analyze(self, context: AnalysisContext) -> ModuleResult: ...
