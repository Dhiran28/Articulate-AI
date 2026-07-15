"""
The LLM abstraction layer's error hierarchy (Sprint 4.4).

Same reason/message principle used everywhere else in this codebase
(AudioValidationError, TranscriptionError, AnalysisError) — but exposed
here as an actual class hierarchy, not just an enum on one exception
type, so a caller can catch either the general `LLMError` (and branch on
`.reason`) or a specific subclass (`except LLMSchemaError:`), whichever
fits. Every subclass fixes its own `reason` — a caller never has to
remember which enum value pairs with which exception.

Nothing in this file talks to a real provider — it's pure vocabulary,
usable identically whether the eventual provider is OpenAI, Anthropic,
Gemini, Ollama, or a local model.
"""

from enum import Enum
from typing import Any


class LLMErrorReason(str, Enum):
    LLM_TIMEOUT = "llm_timeout"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    LLM_INVALID_RESPONSE = "llm_invalid_response"
    LLM_SCHEMA_ERROR = "llm_schema_error"
    PROMPT_NOT_FOUND = "prompt_not_found"
    NO_PROVIDER_CONFIGURED = "no_provider_configured"


class LLMError(Exception):
    """
    Base of the hierarchy. Every subclass below sets `reason` as a class
    attribute — never passed in by the caller — so the mapping from
    exception type to machine-readable reason can't drift out of sync.

    `raw_response` is preserved (never surfaced to an end user) for the
    two failure modes where "what did the provider actually say" matters
    for debugging: an unparseable or schema-invalid response. Mirrors
    ADR 003 §7's "keep the evidence, don't just swallow the failure" —
    the same principle ADR 002 applied to raw provider responses.
    """

    reason: LLMErrorReason

    def __init__(self, message: str, *, raw_response: str | None = None, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.raw_response = raw_response
        self.details = details or {}
        super().__init__(message)


class LLMTimeoutError(LLMError):
    """The provider call did not complete within the configured timeout."""

    reason = LLMErrorReason.LLM_TIMEOUT


class LLMProviderError(LLMError):
    """
    The provider call failed outright — connection error, non-timeout
    exception raised by the provider, rate limit, etc. Distinct from
    LLMTimeoutError so a caller can tell "took too long" apart from
    "failed for some other reason" without inspecting message text.
    """

    reason = LLMErrorReason.LLM_PROVIDER_ERROR


class LLMInvalidResponseError(LLMError):
    """
    The provider returned a response that isn't valid JSON at all (after
    stripping an optional markdown code fence — see response_parser.py).
    Never force-repaired or guessed at.
    """

    reason = LLMErrorReason.LLM_INVALID_RESPONSE


class LLMSchemaError(LLMError):
    """
    The provider's response WAS valid JSON, but didn't match the schema
    the caller required — missing fields, wrong types, unexpected shape.
    Kept distinct from LLMInvalidResponseError because these are two
    different failure moments (parsing vs. validating) with two
    different likely causes (a broken response vs. a model that didn't
    follow instructions).
    """

    reason = LLMErrorReason.LLM_SCHEMA_ERROR


class PromptNotFoundError(LLMError):
    """No prompt is registered under the requested identifier."""

    reason = LLMErrorReason.PROMPT_NOT_FOUND


class NoProviderConfiguredError(LLMError):
    """
    A reasoner (or whatever wires one up) was asked to run without a
    real LLMProvider available. Sprint 4.4 builds no concrete provider,
    so this is exercised today only via explicit `provider=None`-style
    construction — it becomes meaningfully reachable once a future
    sprint adds provider selection driven by configuration (e.g. no
    API key set for any configured provider).
    """

    reason = LLMErrorReason.NO_PROVIDER_CONFIGURED
