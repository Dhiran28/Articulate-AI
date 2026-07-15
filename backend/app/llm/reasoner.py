"""
LLMReasoner (Sprint 4.4): "prompt identifier + context in, validated
structured data out" — the seam ADR 003 named ("prompt in, structured
judgment out") and Sprint 4.4 fully specifies.

Deliberately domain-agnostic: this module has never heard of a
transcript. `reason()` accepts a plain `context: dict[str, object]` of
template variables, not a TranscriptProcessingResult — importing that
model here would make app/llm depend on the CIE's domain models, which
is exactly backwards from ADR 003 §3's design ("app/llm/ ... depended on
by both engines below; depends on neither"). A future reasoning module
is responsible for turning a TranscriptProcessingResult into whatever
`context` dict its prompt template needs (e.g.
`{"transcript": raw.processed_transcript.text}`) — that translation
happens on the caller's side, not inside this generic layer.
"""

import logging
import time
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .errors import LLMError, LLMProviderError, NoProviderConfiguredError
from .prompt_registry import PromptRegistry
from .provider import LLMProvider
from .response_parser import parse_json_response
from .retry_policy import RetryPolicy
from .schema_validator import validate_schema
from .timeout_policy import TimeoutPolicy

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMReasoner(Protocol):
    """
    The interface a caller (a future reasoning module, or ReasoningPass
    once it exists) programs against. `DefaultLLMReasoner` below is
    Sprint 4.4's one implementation; a test can substitute a fake
    satisfying this same shape without touching any real infrastructure.
    """

    async def reason(self, prompt_id: str, context: dict[str, Any], schema: type[T]) -> T: ...


class DefaultLLMReasoner:
    """
    Composes every other piece this sprint built into one pipeline:

      1. Look up `prompt_id` in the PromptRegistry (PromptNotFoundError
         if unknown).
      2. Render the prompt template with `context`.
      3. Call the provider. Each individual attempt is wrapped in
         TimeoutPolicy (so one hung call can never block forever), and
         the whole attempt is wrapped in RetryPolicy, which by default
         only retries LLMProviderError — not LLMTimeoutError. A timeout
         is a signal the configured limit may itself be wrong, not
         automatically a transient blip; a caller that wants timeouts
         retried too can pass `retry_on=(LLMProviderError,
         LLMTimeoutError)` explicitly. A schema or JSON-parsing failure
         is never retried either way — sending the exact same prompt to
         the exact same model again will not produce a different, valid
         answer.
      4. Parse the raw text response into JSON (LLMInvalidResponseError
         on failure).
      5. Validate the parsed JSON against `schema` (LLMSchemaError on
         failure).

    Every exception this raises is a subclass of LLMError — a caller
    never has to catch a raw ValueError, JSONDecodeError, or provider
    SDK exception directly.
    """

    def __init__(
        self,
        provider: LLMProvider | None,
        prompt_registry: PromptRegistry,
        *,
        retry_policy: RetryPolicy | None = None,
        timeout_policy: TimeoutPolicy | None = None,
    ) -> None:
        if provider is None:
            raise NoProviderConfiguredError("No LLMProvider was supplied to this reasoner.")

        self._provider = provider
        self._prompt_registry = prompt_registry
        self._retry_policy = retry_policy or RetryPolicy()
        self._timeout_policy = timeout_policy or TimeoutPolicy()

    async def reason(self, prompt_id: str, context: dict[str, Any], schema: type[T]) -> T:
        """
        Milestone 5.1 adds one consolidated log line per call (success or
        failure) here — this is the one seam every current LLM caller
        (`ReasoningPass`, `CoachingEngine`) goes through, so logging it
        once here covers both rather than duplicating the same log
        statement in each caller.

        `session_id` is read from `context.get("session_id")`, an
        optional, purely diagnostic convention — never a template
        variable this method requires. A caller that wants request
        correlation in these logs includes `"session_id"` in the
        `context` dict it builds (see `ReasoningPass._build_template_context`
        and `CoachingEngine.generate`); a caller that doesn't just logs
        `"unknown"`. This keeps `LLMReasoner` domain-agnostic — it still
        has no idea what a transcript is — while giving every real caller
        an easy way to opt in.
        """
        session_id = context.get("session_id", "unknown")
        start = time.monotonic()
        prompt_version = "unknown"

        try:
            template = self._prompt_registry.get(prompt_id)  # raises PromptNotFoundError
            prompt_version = template.metadata.version if template.metadata else "unknown"
            prompt = template.render(context)

            async def _attempt() -> str:
                return await self._timeout_policy.run(lambda: self._call_provider(prompt))

            raw_text = await self._retry_policy.run(_attempt, retry_on=(LLMProviderError,))

            parsed = parse_json_response(raw_text)
            result = validate_schema(parsed, schema, raw_response=raw_text)
        except LLMError as exc:
            self._log_failure(session_id, prompt_id, prompt_version, time.monotonic() - start, exc)
            raise

        self._log_success(session_id, prompt_id, prompt_version, time.monotonic() - start)
        return result

    async def _call_provider(self, prompt: str) -> str:
        try:
            return await self._provider.generate(prompt)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"{self._provider.provider_name} ({self._provider.model_name}) failed to generate a response.",
            ) from exc

    def _log_success(self, session_id: Any, prompt_id: str, prompt_version: str, elapsed_seconds: float) -> None:
        # Read immediately after the awaited call chain above returns, with
        # no further `await` in between — safe even if `self._provider` is
        # a singleton shared across concurrent requests, since nothing else
        # can run on this event loop between that call finishing and this
        # line (see app/llm/providers/*.py's `last_usage` docstrings for
        # the fuller explanation of this attribute).
        usage = getattr(self._provider, "last_usage", None) or {}
        logger.info(
            "llm_call session_id=%s provider=%s model=%s prompt_id=%s prompt_version=%s "
            "latency_ms=%.1f prompt_tokens=%s completion_tokens=%s total_tokens=%s status=ok",
            session_id,
            self._provider.provider_name,
            self._provider.model_name,
            prompt_id,
            prompt_version,
            elapsed_seconds * 1000,
            usage.get("prompt_tokens", "n/a"),
            usage.get("completion_tokens", "n/a"),
            usage.get("total_tokens", "n/a"),
        )

    def _log_failure(
        self, session_id: Any, prompt_id: str, prompt_version: str, elapsed_seconds: float, exc: LLMError
    ) -> None:
        logger.error(
            "llm_call session_id=%s provider=%s model=%s prompt_id=%s prompt_version=%s "
            "latency_ms=%.1f status=error reason=%s message=%s",
            session_id,
            self._provider.provider_name,
            self._provider.model_name,
            prompt_id,
            prompt_version,
            elapsed_seconds * 1000,
            exc.reason.value,
            exc.message,
        )
