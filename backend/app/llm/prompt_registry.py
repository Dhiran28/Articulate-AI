"""
PromptRegistry (Sprint 4.4): the collection of loaded prompts, keyed by
identifier ("structure_v1", "clarity_v1", "topic_drift_v1", ...).
Deliberately the same shape as ModuleRegistry (app/analysis/registry.py)
— register/discover/get, duplicate registration rejected rather than
silently overwriting — because the two problems are structurally
identical: a named collection of things, looked up by a stable id, where
a naming collision should be loud, not silent.
"""

from pathlib import Path

from .errors import PromptNotFoundError
from .prompt_loader import PromptLoader, PromptTemplate


class DuplicatePromptError(Exception):
    """
    Raised when something tries to register a second prompt under an
    identifier that's already registered. A wiring bug caught at
    registration time, not a per-request failure — same reasoning as
    ModuleRegistry.DuplicateModuleError.
    """

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"A prompt named {identifier!r} is already registered.")


class PromptRegistry:
    def __init__(self, loader: PromptLoader | None = None) -> None:
        self._loader = loader or PromptLoader()
        self._prompts: dict[str, PromptTemplate] = {}

    def register(self, identifier: str, path: Path) -> None:
        """Loads `path` immediately and registers it under `identifier`."""
        if identifier in self._prompts:
            raise DuplicatePromptError(identifier)
        self._prompts[identifier] = self._loader.load(identifier, path)

    def discover_directory(self, directory: Path, pattern: str = "*.md") -> list[str]:
        """
        Bulk-registers every file matching `pattern` in `directory`,
        using each file's stem as its identifier (e.g. `structure_v1.md`
        registers as `"structure_v1"`). Returns the identifiers that
        were registered, in the order discovered, for callers that want
        to log or verify what got picked up.

        A future reasoning-module sprint's real prompt files (ADR 003
        §3's `analysis/reasoning_pass/prompts/`) are expected to be
        loaded this way at application startup, once that package
        exists — this sprint only builds the mechanism.
        """
        registered: list[str] = []
        for path in sorted(directory.glob(pattern)):
            self.register(path.stem, path)
            registered.append(path.stem)
        return registered

    def get(self, identifier: str) -> PromptTemplate:
        template = self._prompts.get(identifier)
        if template is None:
            raise PromptNotFoundError(f"No prompt is registered under identifier {identifier!r}.")
        return template

    def discover(self) -> list[str]:
        """Every currently registered identifier, in registration order."""
        return list(self._prompts.keys())

    def clear(self) -> None:
        self._prompts.clear()

    def __len__(self) -> int:
        return len(self._prompts)

    def __contains__(self, identifier: str) -> bool:
        return identifier in self._prompts
