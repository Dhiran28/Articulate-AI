"""
build_provider() (Milestone 5.1): the one function that turns
`Settings.llm_provider` into a real `LLMProvider`, or `None`.

Two genuinely different "no provider" outcomes, both landing on `None`
today for the same reason Sprint 4.4/Milestone 5's `get_llm_provider()`
already established — a `None` provider is a supported, fully-degraded
application state, not an error state:

  - `LLM_PROVIDER` unset (`""`, the default): nothing was asked for.
    Every deployment of this app has worked this way since Sprint 4.4;
    this sprint doesn't change that default.
  - `LLM_PROVIDER` set to a recognized vendor, but that vendor's
    credential isn't configured (e.g. `LLM_PROVIDER=anthropic` with no
    `ANTHROPIC_API_KEY`): logged as a warning and treated the same as
    "not configured," not a crash — matching `OpenAIWhisperProvider`'s
    established fail-fast-on-*use*, not fail-on-*construction*, style
    for this same situation (this function instead fails on
    construction, by returning `None`, since `LLMProvider | None` is
    already the load-bearing type every downstream consumer expects —
    see app/core/dependencies.py's `get_llm_reasoner()`).

An `LLM_PROVIDER` set to something unrecognized (a typo) is different:
that's a configuration mistake, not a legitimate "not configured" state,
so it raises `UnknownProviderError` immediately rather than silently
behaving like no provider was ever requested — the same "loud, specific
failure for a programmer/config error" discipline
`DuplicateModuleError` / `DuplicatePromptError` already hold elsewhere
in this codebase.
"""

import logging

from app.core.config import Settings
from app.llm.provider import LLMProvider

from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

# One conservative default model per vendor, used only when LLM_MODEL is
# left blank — never silently overriding an explicitly configured model.
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.1",
}

_ADAPTERS = ("openai", "anthropic", "gemini", "ollama")


class UnknownProviderError(ValueError):
    """`LLM_PROVIDER` is set to a value none of the four adapters recognize."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(
            f"Unknown LLM_PROVIDER {provider!r}. Expected one of {', '.join(_ADAPTERS)}, or empty."
        )


def build_provider(settings: Settings) -> LLMProvider | None:
    provider_name = settings.llm_provider.strip().lower()

    if not provider_name:
        return None

    if provider_name not in _ADAPTERS:
        raise UnknownProviderError(settings.llm_provider)

    model = settings.llm_model.strip() or DEFAULT_MODELS[provider_name]

    if provider_name == "ollama":
        # No credential to check — see this module's docstring.
        return OllamaProvider(
            settings.ollama_base_url,
            model,
            temperature=settings.llm_temperature,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    api_key = settings.llm_api_key_for(provider_name)
    if not api_key:
        logger.warning(
            "LLM_PROVIDER=%s but no credential is configured for it; "
            "falling back to no LLM provider (metric-only analysis).",
            provider_name,
        )
        return None

    if provider_name == "openai":
        return OpenAIProvider(
            api_key, model, temperature=settings.llm_temperature, timeout_seconds=settings.llm_timeout_seconds
        )
    if provider_name == "anthropic":
        return AnthropicProvider(
            api_key, model, temperature=settings.llm_temperature, timeout_seconds=settings.llm_timeout_seconds
        )
    # provider_name == "gemini"
    return GeminiProvider(
        api_key, model, temperature=settings.llm_temperature, timeout_seconds=settings.llm_timeout_seconds
    )
