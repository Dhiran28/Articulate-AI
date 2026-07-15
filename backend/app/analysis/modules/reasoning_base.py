"""
_BaseReasoningModule (Sprint 4.5): the shared orchestration every
semantic reasoning module (StructureModule, ClarityModule,
LogicalFlowModule, TopicDriftModule, ConfidenceModule,
ConcisenessModule — see the sibling files in this package) subclasses,
the same way Sprint 4.3's four Metric modules each independently
implemented their own `analyze()` because a Metric module's logic is
each genuinely different. A Reasoning module's *orchestration* — call
the shared LLMReasoner, catch its errors, shape a ModuleResult — is
identical across all six; only *what goes into the prompt* differs. This
class captures the identical part once; each subclass supplies only
`prompt_id` and `_build_template_context()`.

Every concrete reasoning module:
  - is a REASONING module (module_type = ModuleType.REASONING)
  - is constructed with an injected LLMReasoner (app/llm/reasoner.py) —
    never a concrete provider, never an API key; this class has no idea
    what LLM backend is behind the reasoner it was handed
  - validates its LLM output against the one shared ReasoningResult
    schema (models.py) — no module defines its own bespoke output shape,
    which structurally enforces this sprint's "no scores" requirement:
    ReasoningResult only has label/explanation/evidence, nothing a
    module could smuggle a numeric score into
  - never calls an LLM provider directly; every call flows through
    `self._reasoner.reason(...)`, satisfying Sprint 4.5's explicit
    "no module should directly call an LLM provider" requirement

A note on ADR 003's batching mandate: `self._reasoner.reason()` is
called once per module here — each of the six concrete reasoning
modules makes its own independent call through the shared LLMReasoner
abstraction, not one combined request. That satisfies this class's own
mandate ("no module talks to a provider directly," "must flow through
LLMReasoner") but does NOT implement ADR 003's separate, larger
requirement that reasoning modules share one batched LLM request by
default. That's a disclosed, deliberate scope decision for this sprint,
not an oversight — see docs/decisions/003-*.md's Sprint 4.5 revision
note and this sprint's completion summary for the full reasoning.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.llm.errors import LLMError
from app.llm.reasoner import LLMReasoner

from ..errors import AnalysisErrorReason
from ..models import AnalysisContext, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ReasoningResult, ResultMetadata


class _BaseReasoningModule(ABC):
    """
    Common `analyze()` for every Reasoning module. A subclass must set
    the class attributes `module_name`, `prompt_id`, and `metadata`, and
    implement `_build_template_context()` — everything else is handled
    here identically for all six modules.
    """

    module_type = ModuleType.REASONING

    module_name: str
    prompt_id: str
    metadata: dict[str, Any]

    def __init__(self, reasoner: LLMReasoner) -> None:
        self._reasoner = reasoner

    @abstractmethod
    def _build_template_context(self, context: AnalysisContext) -> dict[str, Any]:
        """
        Turns the AnalysisContext this module received into the flat
        `dict[str, object]` of `$variable` values its own prompt template
        needs (see app/llm/prompt_loader.py's PromptTemplate.render).
        This is the one piece of real per-module logic — deciding which
        parts of the transcript, which deterministic metrics, and which
        reasoning_context entries actually belong in *this* module's
        prompt — and is deliberately left to each subclass rather than
        guessed at generically here.
        """
        raise NotImplementedError

    async def analyze(self, context: AnalysisContext) -> ModuleResult:
        template_context = self._build_template_context(context)

        try:
            result = await self._reasoner.reason(self.prompt_id, template_context, ReasoningResult)
        except LLMError as exc:
            # LLMErrorReason and AnalysisErrorReason deliberately share
            # identical string values (see errors.py's Sprint 4.5
            # comment) precisely so this translation is a direct,
            # lossless one-line mapping rather than a hand-maintained
            # branch per error type.
            return ModuleResult(
                metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
                status=ModuleStatus.FAILED,
                error=ModuleErrorDetail(
                    reason=AnalysisErrorReason(exc.reason.value),
                    message=exc.message,
                ),
            )

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            reasoning=result,
        )
