"""
LLMProvider (Sprint 4.4): the seam every concrete vendor integration
implements. Deliberately the smallest possible surface — the same
"provider does one thing, everything else lives above it" shape as
TranscriptionProvider (app/transcription/providers/base.py).

No vendor is hardcoded or even referenced here. OpenAI, Anthropic,
Google Gemini, Ollama, and self-hosted local models are all equally
"a thing that turns a prompt string into a text response" from this
layer's point of view — see this package's README for how a future
provider plugs in without anything in app/llm/ changing.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """
    Every provider exposes exactly four things:

      - `provider_name`: which vendor/backend this is ("openai",
        "anthropic", "ollama", ...) — identifies the provider, not the
        model.
      - `model_name`: which model this instance calls ("gpt-4o",
        "claude-opus-4-8", "llama3.1", ...).
      - `version`: this adapter's own version string — not the vendor's
        API version. Exists for the same reproducibility reason ADR 003
        §5 names prompt versioning: being able to say "this result came
        from provider adapter v1.2" matters when debugging a regression.
      - `generate()`: send a prompt, get raw text back.

    `generate()` returns plain text, not parsed JSON — turning that text
    into validated structured data is response_parser.py and
    schema_validator.py's job (composed by LLMReasoner), not the
    provider's. Keeping the provider this dumb is what makes it trivial
    to implement for a vendor whose SDK doesn't do JSON-mode at all.

    Providers are expected to raise plain exceptions on failure (a
    connection error, an SDK-specific error, whatever); LLMReasoner
    is responsible for classifying those into the LLMError hierarchy —
    a provider adapter is not expected to know about app/llm's own
    error classes.
    """

    provider_name: str
    model_name: str
    version: str

    async def generate(self, prompt: str) -> str: ...
