import logging
from typing import Any

from app.llm.errors import LLMError
from app.transcript_processing.models import TranscriptProcessingResult

from .errors import AnalysisErrorReason
from .modules.base import AnalysisModule
from .modules.section_reasoning_base import REASONING_PASS_RESULT_KEY
from .models import AnalysisContext, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ResultMetadata
from .reasoning_pass.batch import ReasoningPass

logger = logging.getLogger(__name__)


class DuplicateModuleError(Exception):
    """
    Raised when something tries to register a second module under a
    `module_name` that's already registered. This is a wiring bug caught
    at registration time (typically application startup), not a
    per-request analysis failure — so it's a plain exception, not an
    AnalysisErrorReason: nothing about "a transcript failed to analyze"
    applies here, the registry itself was misconfigured.
    """

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        super().__init__(f"A module named {module_name!r} is already registered.")


class ModuleRegistry:
    """
    Owns the collection of analysis modules (ADR 003 §1/§3): registers
    them, makes them discoverable, and executes all of them against a
    transcript with per-module failure isolation. `AnalysisEngine`
    (engine.py) is a thin layer on top of this — the guard check and
    `AnalysisReport` assembly live there; running the modules themselves
    lives here.

    Registration order is preserved (backed by a plain dict, which
    Python guarantees iterates in insertion order) and is what
    `discover()` and `execute()` both use — so "the order modules were
    registered in" is also "the order they run in," a single, obvious
    rule rather than something a caller has to reason about separately.
    """

    def __init__(self, reasoning_pass: ReasoningPass | None = None) -> None:
        self._modules: dict[str, AnalysisModule] = {}
        self._reasoning_pass = reasoning_pass
        """
        Sprint 4.5.1: the one shared component that makes the one LLM
        call every REASONING module's result now comes from — see
        `reasoning_pass/batch.py`. Optional and defaulting to `None`
        (matching every other not-yet-wired-up dependency in this
        codebase, e.g. `DefaultLLMReasoner`'s own `provider=None` guard)
        so a registry with only Metric modules, or a test, never has to
        construct one just to be valid. A registry with REASONING
        modules registered but no `reasoning_pass` configured degrades
        per-module (see `execute()`) rather than raising — the same
        "partial results over a hard failure" principle ADR 003 §7
        already applies to a crashing module.
        """

    def register(self, module: AnalysisModule) -> None:
        """
        Adds a module. Raises DuplicateModuleError if `module.module_name`
        is already registered — silently overwriting an existing
        registration would let a naming collision between two modules
        hide one of them with no signal that it happened.
        """
        if module.module_name in self._modules:
            raise DuplicateModuleError(module.module_name)
        self._modules[module.module_name] = module

    def discover(self) -> list[AnalysisModule]:
        """Every currently registered module, in registration order."""
        return list(self._modules.values())

    def get(self, module_name: str) -> AnalysisModule | None:
        return self._modules.get(module_name)

    def clear(self) -> None:
        """
        Removes every registered module. Exists for test isolation (the
        same reason Sprint 3.6's conftest.py clears lru_cache'd
        singletons between tests) — not expected to be called by
        production code paths.
        """
        self._modules.clear()

    def __len__(self) -> int:
        return len(self._modules)

    def __contains__(self, module_name: str) -> bool:
        return module_name in self._modules

    async def execute(
        self,
        transcript: TranscriptProcessingResult,
        reasoning_context: dict[str, Any] | None = None,
    ) -> list[ModuleResult]:
        """
        Runs every registered module against `transcript` and returns one
        ModuleResult per module.

        Two-phase run (Sprint 4.5), now with a batched LLM step between
        the two phases (Sprint 4.5.1):

          Phase 1 — every METRIC module runs first, in registration order,
          each given an AnalysisContext whose `metrics` dict is empty
          (nothing has run yet). Every METRIC result, keyed by
          module_name, is collected into a `metrics` dict as it completes.

          Between phases — if any REASONING module is registered, this
          registry runs `self._reasoning_pass` **exactly once** (not once
          per module) and stashes its result into
          `reasoning_context[REASONING_PASS_RESULT_KEY]` before phase 2
          starts. Every REASONING module's own `analyze()` then simply
          reads its own section back out — see
          `modules/section_reasoning_base.py`. This is what "only one LLM
          request per analysis" (Sprint 4.5.1) actually means at the
          registry level: `ReasoningPass.run()` is called at most once
          per `execute()` call, full stop, regardless of how many
          REASONING modules are registered.

          Phase 2 — every non-METRIC module (i.e. REASONING) runs next, in
          registration order, each given an AnalysisContext whose
          `metrics` dict is fully populated from phase 1 and whose
          `reasoning_context` carries the batched result from the step
          above (when available).

        Two degraded paths, both per-module rather than a hard failure of
        the whole request (ADR 003 §7's "partial results over an all-or-
        nothing failure" principle):
          - **No `reasoning_pass` configured** (`self._reasoning_pass is
            None`) but REASONING modules are registered: each such module
            gets a `failed` ModuleResult (`NO_PROVIDER_CONFIGURED`)
            without `analyze()` ever being called — there's nothing
            meaningful to hand it. METRIC modules are unaffected.
          - **The one combined call itself fails** (`ReasoningPass.run()`
            raises an `LLMError`): every currently-registered REASONING
            module gets a `failed` ModuleResult carrying that same
            translated reason (`LLMErrorReason` and `AnalysisErrorReason`
            share identical string values — see errors.py), again without
            `analyze()` being called. This is ADR 003 §7's named
            "batch-level failure" tradeoff made real: one call failing
            now fails every reasoning dimension together, in exchange for
            the five-out-of-six-calls-saved cost/latency win the rest of
            the time. METRIC modules are still unaffected either way — an
            `AnalysisReport` from a batch failure is never entirely
            empty.

        The overall returned order is "all METRIC results, then all
        REASONING results" — registration order preserved within each
        phase. `reasoning_context` passed into this method is merged with
        (and never overwrites anything other than) the reserved
        `REASONING_PASS_RESULT_KEY` this registry itself writes.

        A module that raises never stops the others from running and
        never propagates out of this method (ADR 003 §7) — it's caught
        here and converted into a `failed` ModuleResult with reason
        MODULE_ERROR, the same isolation AnalysisEngine relied on before
        this responsibility moved into the registry itself.
        """
        modules = self.discover()
        metric_modules = [m for m in modules if m.module_type is ModuleType.METRIC]
        reasoning_modules = [m for m in modules if m.module_type is not ModuleType.METRIC]
        context_extras = dict(reasoning_context or {})

        results: list[ModuleResult] = []
        metrics: dict[str, ModuleResult] = {}

        metric_phase_context = AnalysisContext(transcript=transcript, metrics={}, reasoning_context=context_extras)
        for module in metric_modules:
            result = await self._run_one(module, metric_phase_context)
            results.append(result)
            metrics[module.module_name] = result

        if reasoning_modules:
            batch_failure: ModuleErrorDetail | None = None

            if self._reasoning_pass is None:
                batch_failure = ModuleErrorDetail(
                    reason=AnalysisErrorReason.NO_PROVIDER_CONFIGURED,
                    message="No shared ReasoningPass was configured for this registry.",
                )
            else:
                pre_batch_context = AnalysisContext(
                    transcript=transcript, metrics=metrics, reasoning_context=context_extras
                )
                try:
                    batched_result = await self._reasoning_pass.run(pre_batch_context)
                except LLMError as exc:
                    # See analysis/errors.py's Sprint 4.5 comment: the two
                    # enums deliberately share identical string values, so
                    # this is a direct, lossless one-line mapping.
                    batch_failure = ModuleErrorDetail(
                        reason=AnalysisErrorReason(exc.reason.value),
                        message=exc.message,
                    )
                else:
                    context_extras = {**context_extras, REASONING_PASS_RESULT_KEY: batched_result}

            if batch_failure is not None:
                for module in reasoning_modules:
                    results.append(
                        ModuleResult(
                            metadata=ResultMetadata(module_name=module.module_name, module_type=module.module_type),
                            status=ModuleStatus.FAILED,
                            error=batch_failure,
                        )
                    )
                return results

        reasoning_phase_context = AnalysisContext(
            transcript=transcript, metrics=metrics, reasoning_context=context_extras
        )
        for module in reasoning_modules:
            results.append(await self._run_one(module, reasoning_phase_context))

        return results

    async def _run_one(self, module: AnalysisModule, context: AnalysisContext) -> ModuleResult:
        try:
            return await module.analyze(context)
        except Exception:
            logger.exception("Analysis module %s raised during analyze()", module.module_name)
            return ModuleResult(
                metadata=ResultMetadata(module_name=module.module_name, module_type=module.module_type),
                status=ModuleStatus.FAILED,
                error=ModuleErrorDetail(
                    reason=AnalysisErrorReason.MODULE_ERROR,
                    message="This module failed unexpectedly and could not complete.",
                ),
            )


# Module-level default instance — the one place production code registers
# a real module (once real modules exist; empty today, see modules/).
# AnalysisEngine accepts an injected ModuleRegistry too, so tests can
# exercise a fresh, isolated registry instead of mutating this shared one.
MODULE_REGISTRY = ModuleRegistry()
