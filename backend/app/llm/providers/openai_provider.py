"""
OpenAIProvider (Milestone 5.1): calls OpenAI's Chat Completions API.

Same "fail fast, no client if no key" shape as
`app/transcription/providers/openai_whisper.py`'s `OpenAIWhisperProvider`
— a deliberate, repeated convention in this codebase rather than a
coincidence, so a reader who already understands one provider adapter
recognizes the other immediately.
"""

import logging

from openai import AsyncOpenAI, OpenAIError

logger = logging.getLogger(__name__)


class OpenAIProvider:
    provider_name = "openai"
    version = "1.0.0"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        temperature: float = 0.3,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model_name = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds) if api_key else None
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

        # The most recent call's token usage, normalized to
        # {"prompt_tokens", "completion_tokens", "total_tokens"} — read by
        # `DefaultLLMReasoner.reason()` immediately after each call for
        # its one consolidated log line (see app/llm/reasoner.py). `None`
        # until a call succeeds, or if OpenAI's response didn't include
        # usage. Not part of the `LLMProvider` Protocol — a diagnostic
        # extra, safe for `LLMReasoner` to read via `getattr(..., None)`
        # and for any fake/test provider to simply not have.
        self.last_usage: dict[str, int] | None = None

    async def generate(self, prompt: str) -> str:
        if self._client is None:
            raise RuntimeError("OpenAIProvider has no API key configured.")

        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._temperature,
                timeout=self._timeout_seconds,
            )
        except OpenAIError:
            logger.exception("OpenAI LLM call failed (model=%s)", self.model_name)
            raise

        usage = response.usage
        self.last_usage = (
            {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }
            if usage is not None
            else None
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty response.")
        return content
