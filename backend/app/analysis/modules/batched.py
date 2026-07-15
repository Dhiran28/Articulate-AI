from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.transcript_processing.models import TranscriptProcessingResult

from ..models import ModuleCategory, ModuleResult


@dataclass
class PromptContribution:
    """
    One BatchedReasoningModule's slice of the single combined reasoning
    request (ADR 003 §1/§5). ReasoningPass — not built this sprint, see
    the module docstring below — collects one of these from every
    registered BatchedReasoningModule, merges them into one prompt, and
    sends exactly one request through LLMReasoner.

    `section_key` must be unique across every registered
    BatchedReasoningModule: it's both the key ReasoningPass uses to
    build the combined output schema and the key it looks up later to
    hand this module back only its own slice of the response.
    """

    section_key: str
    instructions: str
    output_schema: dict[str, Any]


@runtime_checkable
class BatchedReasoningModule(Protocol):
    """
    Per ADR 003 §1: modules that need genuine semantic judgment (a
    filler-word count can't tell you whether an argument holds together)
    but don't each own an LLM call. Splitting "ask the LLM" into two
    steps — contribute() and interpret() — is what lets
    ReasoningPass make exactly one combined call on behalf of every
    registered reasoning module, instead of one call each.

    `contribute()` is pure and synchronous — it only builds this
    module's prompt fragment and output schema from the transcript it's
    given; the actual network call belongs to ReasoningPass, never to an
    individual module.

    `interpret()` is handed *only* this module's own section of the
    combined structured response (see ReasoningPass, once built) and
    turns it into this module's ModuleResult. It never sees any other
    module's section, which is what keeps one module's malformed section
    from affecting any other module's result (ADR 003 §7).

    No implementations exist yet, and neither does ReasoningPass itself —
    Sprint 4.2 scopes only this contract and AnalysisEngine's
    orchestration around it. Building the real batched call (the
    app/llm/ seam and ReasoningPass) is named in ADR 003 §6 as its own,
    separately-scoped next step. Until it exists, AnalysisEngine reports
    any registered BatchedReasoningModule as failed with
    REASONING_PASS_UNAVAILABLE rather than skipping it silently or
    fabricating a result (see engine.py).
    """

    name: str
    category: ModuleCategory

    def contribute(self, transcript: TranscriptProcessingResult) -> PromptContribution: ...

    def interpret(self, section: dict[str, Any], transcript: TranscriptProcessingResult) -> ModuleResult: ...
