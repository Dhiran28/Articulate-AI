from typing import Any, Protocol, runtime_checkable

from app.transcript_processing.models import TranscriptProcessingResult

from ..models import ModuleResult, ModuleType


@runtime_checkable
class AnalysisModule(Protocol):
    """
    Sprint 4.2's one required module contract (ADR 003 §1's module
    concept, deliberately unified for this scaffolding sprint rather
    than split by how a future module gets its judgment). Every module —
    whether it ends up METRIC or REASONING — implements the same shape:

      - `module_name`: a unique identifier (see ModuleRegistry —
        duplicate names are rejected at registration).
      - `module_type`: METRIC or REASONING (models.ModuleType) — a
        convention for dispatch/reporting, not a constraint this
        Protocol enforces structurally.
      - `metadata`: free-form static info the module exposes about
        itself (e.g. a version or short description) — distinct from
        ResultMetadata (models.py), which is provenance attached to a
        *result*, not the module's own self-description.
      - `analyze()`: given a transcript, return this module's
        ModuleResult.

    `@runtime_checkable` lets ModuleRegistry and AnalysisEngine verify a
    registered object actually satisfies this shape with a plain
    isinstance() check.

    No implementations exist yet — Sprint 4.2 explicitly builds
    scaffolding only, not real modules (ADR 003 §2 lists the ten
    dimensions this will eventually house).

    A note on where ADR 003's "reasoning modules should not
    independently call the LLM by default" requirement goes from here:
    it isn't a second Protocol shape in this sprint. A future REASONING
    module still implements `analyze()` like any other module; the
    "share one LLM call across modules" behavior becomes an
    implementation detail of *how* several reasoning modules' analyze()
    calls coordinate through a shared component (introduced in the
    sprint that actually builds LLM integration), not a different
    interface at the registry/engine level. Keeping one uniform contract
    now is what lets the registry and engine be batching-mechanism
    agnostic entirely.
    """

    module_name: str
    module_type: ModuleType
    metadata: dict[str, Any]

    async def analyze(self, transcript: TranscriptProcessingResult) -> ModuleResult: ...
