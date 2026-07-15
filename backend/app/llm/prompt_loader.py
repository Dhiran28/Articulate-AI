"""
PromptLoader (Sprint 4.4): reads a prompt template from a markdown/text
file on disk. No prompt text lives as a Python string literal anywhere
in this codebase's LLM layer — a prompt is content, not code, and
editing one should never require touching a .py file.

Deliberately stateless and single-purpose: "given a path, read and wrap
one file." Keeping a collection of loaded prompts, looking them up by
identifier, and preventing duplicate registration is PromptRegistry's
job (prompt_registry.py), not this module's.
"""

from dataclasses import dataclass
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class PromptTemplate:
    """
    One loaded prompt file. `render()` substitutes `$variable`-style
    placeholders (Python's stdlib string.Template syntax) rather than
    `.format()`-style `{variable}` placeholders deliberately: a prompt
    that includes an example JSON output block — very likely, since
    every reasoning prompt asks for structured JSON back — is full of
    literal `{` and `}` characters that `.format()` would misinterpret
    as placeholders. `$variable` doesn't collide with JSON braces at
    all, so prompt authors never have to escape anything.
    """

    identifier: str
    path: Path
    raw_text: str

    def render(self, variables: dict[str, object]) -> str:
        """
        Substitutes every `$variable` in the template. Raises a plain
        `KeyError`-derived `ValueError` if the template references a
        variable the caller didn't supply — a silently half-rendered
        prompt sent to an LLM is worse than a loud failure before it's
        ever sent.
        """
        try:
            return Template(self.raw_text).substitute(variables)
        except KeyError as exc:
            raise ValueError(
                f"Prompt {self.identifier!r} references variable {exc} which was not provided."
            ) from exc


class PromptLoader:
    """Reads one prompt file at a time into a PromptTemplate."""

    def load(self, identifier: str, path: Path) -> PromptTemplate:
        if not path.is_file():
            raise FileNotFoundError(f"No prompt file at {path}")

        raw_text = path.read_text(encoding="utf-8")
        return PromptTemplate(identifier=identifier, path=path, raw_text=raw_text)
