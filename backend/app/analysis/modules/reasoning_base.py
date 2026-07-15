"""
_BaseReasoningModule (Sprint 4.5, repurposed Sprint 4.5.1): originally
the shared orchestration all six concrete reasoning modules subclassed,
each independently calling the shared `LLMReasoner` — six calls per
analysis. Sprint 4.5.1 replaced that per-module-call design with
`ReasoningPass` (reasoning_pass/batch.py), which makes one combined call
for all six dimensions at once; the six concrete modules
(`StructureModule`, `ClarityModule`, `LogicalFlowModule`,
`TopicDriftModule`, `ConfidenceModule`, `ConcisenessModule`) now
subclass `_SectionReasoningModule` (`section_reasoning_base.py`)
instead, and no longer use this class at all.

This class is kept, not deleted, because it is exactly ADR 003 §1's
"deep analysis" escape hatch: a future reasoning dimension whose needs
don't fit the shared batched prompt (multi-turn back-and-forth, tool
use, a much longer context than the other dimensions comfortably share)
can still subclass `_BaseReasoningModule` and make its own independent
`LLMReasoner` call, exactly as every reasoning module did before Sprint
4.5.1 — that option is real, tested infrastructure (see
`tests/test_reasoning_base_escape_hatch.py`), not just documented intent.
No concrete module in this codebase uses it today.

Every concrete subclass of this class still would:
  - be a REASONING module (module_type = ModuleType.REASONING)
  - be constructed with an injected LLMReasoner (app/llm/reasoner.py) —
    never a concrete provider, never an API key
  - validate its LLM output against the one shared ReasoningResult
    schema (models.py) — no bespoke output shape, structurally ruling
    out a smuggled-in numeric score
  - never call an LLM provider directly; every call flows through
    `self._reasoner.reason(...)`
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
