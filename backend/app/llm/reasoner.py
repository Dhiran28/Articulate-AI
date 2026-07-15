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

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .errors import LLMProviderError, NoProviderConfiguredError
from .prompt_registry import PromptRegistry
from .provider import LLMProvider
from .response_parser import parse_json_response
from .retry_policy import RetryPolicy
from .schema_validator import validate_schema
from .timeout_policy import TimeoutPolicy

T = TypeVar("T", bound=BaseModel)


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
        template = self._prompt_registry.get(prompt_id)  # raises PromptNotFoundError
        prompt = template.render(context)

        async def _attempt() -> str:
            return await self._timeout_policy.run(lambda: self._call_provider(prompt))

        raw_text = await self._retry_policy.run(_attempt, retry_on=(LLMProviderError,))

        parsed = parse_json_response(raw_text)
        return validate_schema(parsed, schema, raw_response=raw_text)

    async def _call_provider(self, prompt: str) -> str:
        try:
            return await self._provider.generate(prompt)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                f"{self._provider.provider_name} ({self._provider.model_name}) failed to generate a response.",
            ) from exc
