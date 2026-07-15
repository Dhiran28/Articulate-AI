"""
PromptLoader (Sprint 4.4, extended Sprint 4.5): reads a prompt template
from a markdown/text file on disk. No prompt text lives as a Python
string literal anywhere in this codebase's LLM layer — a prompt is
content, not code, and editing one should never require touching a .py
file.

Sprint 4.5 adds mandatory structured metadata: every prompt file must
open with a JSON frontmatter block (id, version, type, expected_output,
model_hints) before its body. JSON rather than YAML deliberately — the
metadata shape is simple and flat enough that a real YAML parser would
be a new third-party dependency for no real benefit; `json.loads` plus
the same pydantic validation every other typed shape in this codebase
already uses is simpler and dependency-free.

Deliberately stateless and single-purpose: "given a path, read, split
off its metadata, and wrap the rest." Keeping a collection of loaded
prompts, looking them up by identifier, and preventing duplicate
registration is PromptRegistry's job (prompt_registry.py), not this
module's.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from pydantic import BaseModel, Field, ValidationError

_FRONTMATTER_PATTERN = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)\Z", re.DOTALL)


class PromptMetadata(BaseModel):
    """
    The structured metadata Sprint 4.5 requires every real prompt file
    to declare. Domain-agnostic on purpose — `type` is a plain string
    (e.g. "analysis", "coaching", "rewrite" — matching this repo's
    prompt category folders), not a hardcoded enum, since app/llm has no
    business knowing what categories the CIE or Coaching Engine choose
    to organize their prompts into. `expected_output` is likewise a
    human/documentation-facing name (e.g. "ReasoningResult"), not a live
    reference to a real Python type — keeping this file decoupled from
    any specific schema class.
    """

    id: str
    version: str
    type: str
    expected_output: str
    model_hints: dict[str, Any] = Field(default_factory=dict)


class PromptFormatError(ValueError):
    """
    Raised when a prompt file is missing its required frontmatter block,
    or the frontmatter isn't valid JSON, or it doesn't satisfy
    PromptMetadata. A prompt without valid, complete metadata is treated
    exactly like any other malformed-input case in this codebase: a
    loud, specific failure at load time, not a warning or a
    best-effort partial load.
    """


@dataclass(frozen=True)
class PromptTemplate:
    """
    One loaded prompt file: its required metadata, plus the renderable
    body (the frontmatter block itself is never part of `raw_text` and
    is never sent to an LLM — it's metadata about the prompt, not part
    of the prompt).

    `render()` substitutes `$variable`-style placeholders (Python's
    stdlib string.Template syntax) rather than `.format()`-style
    `{variable}` placeholders deliberately: a prompt that includes an
    example JSON output block — very likely, since every reasoning
    prompt asks for structured JSON back — is full of literal `{` and
    `}` characters that `.format()` would misinterpret as placeholders.
    `$variable` doesn't collide with JSON braces at all, so prompt
    authors never have to escape anything.
    """

    identifier: str
    path: Path
    raw_text: str
    metadata: PromptMetadata | None = None
    """
    Optional here (not on the file itself — see PromptLoader.load,
    which always requires it for a real file) so tests can construct a
    PromptTemplate in-memory to exercise render() without also having to
    fabricate a metadata block for every case that isn't testing
    metadata itself.
    """

    def render(self, variables: dict[str, object]) -> str:
        """
        Substitutes every `$variable` in the template body. Raises a
        plain `KeyError`-derived `ValueError` if the template references
        a variable the caller didn't supply — a silently half-rendered
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

        raw = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_PATTERN.match(raw)
        if not match:
            raise PromptFormatError(
                f"Prompt file {path} is missing its required JSON frontmatter "
                f"block (id, version, type, expected_output, model_hints)."
            )

        metadata_text, body = match.group(1), match.group(2)

        try:
            metadata_dict = json.loads(metadata_text)
        except json.JSONDecodeError as exc:
            raise PromptFormatError(f"Prompt file {path} has invalid JSON frontmatter: {exc}") from exc

        try:
            metadata = PromptMetadata.model_validate(metadata_dict)
        except ValidationError as exc:
            raise PromptFormatError(f"Prompt file {path} has incomplete frontmatter metadata: {exc}") from exc

        return PromptTemplate(identifier=identifier, path=path, raw_text=body.strip(), metadata=metadata)
