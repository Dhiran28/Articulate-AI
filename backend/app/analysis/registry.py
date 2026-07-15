import logging
from typing import Any

from app.transcript_processing.models import TranscriptProcessingResult

from .errors import AnalysisErrorReason
from .modules.base import AnalysisModule
from .models import AnalysisContext, ModuleErrorDetail, ModuleResult, ModuleStatus, ModuleType, ResultMetadata

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

    def __init__(self) -> None:
        self._modules: dict[str, AnalysisModule] = {}

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

        Sprint 4.5 change (disclosed breaking change to Sprint 4.2's flat
        registration-order execution): this is now a two-phase run, not a
        single pass.

          Phase 1 — every METRIC module runs first, in registration order,
          each given an AnalysisContext whose `metrics` dict is empty
          (nothing has run yet). Every METRIC result, keyed by
          module_name, is collected into a `metrics` dict as it completes.

          Phase 2 — every non-METRIC module (i.e. REASONING) runs next, in
          registration order, each given an AnalysisContext whose
          `metrics` dict is now fully populated with every METRIC result
          from phase 1. This is what lets a Reasoning module (e.g. Sprint
          4.5's ConcisenessModule) use deterministic signal like
          speaking_pace's words-per-minute without calling that module
          itself — it's simply handed the finished result.

        The overall returned order is therefore "all METRIC results, then
        all REASONING results" — no longer strict flat registration order
        across types, though registration order is still preserved within
        each phase. `reasoning_context` is passed straight through to
        every module's AnalysisContext unchanged; it's an open
        extensibility hook this registry doesn't interpret itself.

        A module that raises never stops the others from running and
        never propagates out of this method (ADR 003 §7) — it's caught
        here and converted into a `failed` ModuleResult with reason
        MODULE_ERROR, the same isolation AnalysisEngine relied on before
        this responsibility moved into the registry itself.
        """
        modules = self.discover()
        metric_modules = [m for m in modules if m.module_type is ModuleType.METRIC]
        other_modules = [m for m in modules if m.module_type is not ModuleType.METRIC]
        context_extras = reasoning_context or {}

        results: list[ModuleResult] = []
        metrics: dict[str, ModuleResult] = {}

        metric_phase_context = AnalysisContext(transcript=transcript, metrics={}, reasoning_context=context_extras)
        for module in metric_modules:
            result = await self._run_one(module, metric_phase_context)
            results.append(result)
            metrics[module.module_name] = result

        reasoning_phase_context = AnalysisContext(
            transcript=transcript, metrics=metrics, reasoning_context=context_extras
        )
        for module in other_modules:
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
