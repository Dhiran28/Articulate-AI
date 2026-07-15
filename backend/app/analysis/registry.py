"""
The Module Registry (ADR 003 §1/§3): the one list AnalysisEngine reads
to know which modules to run. Adding a module — Metric, batched
Reasoning, or a future standalone "deep analysis" module — means adding
one entry here; nothing else in this package changes.

Empty for now, deliberately. Sprint 4.2 builds the scaffolding every
future module plugs into (the two Protocols in modules/, the
ModuleResult/AnalysisReport models, and AnalysisEngine's orchestration)
without writing any real module yet. The four Metric modules, the
app/llm/ seam + ReasoningPass, and the six reasoning modules are each
their own, separately-scoped future sprint — see ADR 003's Sprint 4.1
revision notes.
"""

from typing import Union

from .modules.base import AnalysisModule
from .modules.batched import BatchedReasoningModule

RegisteredModule = Union[AnalysisModule, BatchedReasoningModule]

MODULE_REGISTRY: list[RegisteredModule] = []
