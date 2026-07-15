"""
_SectionReasoningModule (Sprint 4.5.1): the shared orchestration every
*current* semantic reasoning module now uses, replacing Sprint 4.5's
`_BaseReasoningModule` (reasoning_base.py) for these six modules
specifically — see that file's own updated docstring for why it still
exists, unused by any concrete module today, as ADR 003 §1's "deep
analysis" escape hatch for a future module that genuinely needs its own
independent LLM call.

Every concrete module subclassing this one (`StructureModule`,
`ClarityModule`, `LogicalFlowModule`, `TopicDriftModule`,
`ConfidenceModule`, `ConcisenessModule`) no longer calls an LLM, and no
longer needs an `LLMReasoner` injected at construction at all —
`ReasoningPass` (reasoning_pass/batch.py) is the only thing in this
codebase that does either, now. A concrete module here does exactly
three things: read its own key out of the `BatchedReasoningResult` that
`ModuleRegistry` already ran `ReasoningPass` to produce, confirm that
section is actually present and well-formed (defensive, not a second
full JSON-schema pass — see below), and return it wrapped in a
`ModuleResult`.
"""

from abc import ABC

from ..errors import AnalysisErrorReason
from ..models import AnalysisContext, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ReasoningResult, ResultMetadata

REASONING_PASS_RESULT_KEY = "reasoning_pass_result"
"""
The single, shared key `ModuleRegistry` stores a completed
`BatchedReasoningResult` under, inside `AnalysisContext.reasoning_context`
(models.py's existing open extensibility hook — this is its first real
use). Defined once, here, and imported by both `registry.py` (which
writes it) and this file (which reads it), so the two sides of that
contract can never drift out of sync by one being a typo'd string
literal.
"""


class _SectionReasoningModule(ABC):
    """
    Common `analyze()` for every section-reading Reasoning module. A
    subclass sets `module_name`, `section_key` (the matching field name
    on `BatchedReasoningResult`), and `metadata` as class or instance
    attributes — there is no `_build_template_context()` to implement
    here, unlike the old `_BaseReasoningModule`, because these modules no
    longer build a prompt at all.
    """

    module_type = ModuleType.REASONING

    module_name: str
    section_key: str
    metadata: dict

    async def analyze(self, context: AnalysisContext) -> ModuleResult:
        batch = context.reasoning_context.get(REASONING_PASS_RESULT_KEY)

        if batch is None:
            # Reached only if a caller runs this module's analyze()
            # directly (e.g. a test, or a mis-wired registry) without
            # ModuleRegistry having populated reasoning_context first —
            # see registry.py's own NO_PROVIDER_CONFIGURED handling for
            # the normal path (no ReasoningPass configured at all), which
            # never reaches here because it skips calling analyze()
            # entirely in that case.
            return self._failed(
                AnalysisErrorReason.NO_PROVIDER_CONFIGURED,
                "No shared reasoning pass result was available in this context.",
            )

        section = getattr(batch, self.section_key, None)

        # Defensive, not a second schema pass: BatchedReasoningResult
        # (batch.py) already required every field to be a valid
        # ReasoningResult for the whole combined response to have
        # validated in the first place (app/llm/schema_validator.py runs
        # once, for the whole object, inside ReasoningPass.run()). This
        # check exists so a module never returns a broken ModuleResult
        # if it's ever handed something other than a real
        # BatchedReasoningResult (e.g. a hand-built fake in a test) —
        # not because a real, validated batch can actually be missing a
        # field.
        if not isinstance(section, ReasoningResult):
            return self._failed(
                AnalysisErrorReason.LLM_SCHEMA_ERROR,
                f"The shared reasoning pass result had no valid {self.section_key!r} section.",
            )

        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.OK,
            reasoning=section,
        )

    def _failed(self, reason: AnalysisErrorReason, message: str) -> ModuleResult:
        return ModuleResult(
            metadata=ResultMetadata(module_name=self.module_name, module_type=self.module_type),
            status=ModuleStatus.FAILED,
            error=ModuleErrorDetail(reason=reason, message=message),
        )
