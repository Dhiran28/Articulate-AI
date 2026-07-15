"""
AnthropicProvider (Milestone 5.1): calls Anthropic's Messages API.
"""

import logging

from anthropic import AnthropicError, AsyncAnthropic

logger = logging.getLogger(__name__)

# The Messages API requires `max_tokens` on every request (unlike OpenAI's
# Chat Completions, where it's optional) — there's no natural "unlimited"
# value to read from Settings, and Milestone 5.1's configuration surface
# deliberately doesn't add a fifth knob (LLM_MAX_TOKENS) beyond what the
# sprint asked for. Fixed here, disclosed rather than silently arbitrary:
# every prompt this application sends asks for a bounded JSON object
# (a BatchedReasoningResult or a CoachingContent), not open-ended prose,
# so a generous fixed ceiling is enough headroom without being unbounded.
_MAX_OUTPUT_TOKENS = 4096


class AnthropicProvider:
    provider_name = "anthropic"
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
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_seconds) if api_key else None
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self.last_usage: dict[str, int] | None = None

    async def generate(self, prompt: str) -> str:
        if self._client is None:
            raise RuntimeError("AnthropicProvider has no API key configured.")

        try:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=_MAX_OUTPUT_TOKENS,
                temperature=self._temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except AnthropicError:
            logger.exception("Anthropic LLM call failed (model=%s)", self.model_name)
            raise

        usage = response.usage
        self.last_usage = (
            {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.input_tokens + usage.output_tokens,
            }
            if usage is not None
            else None
        )

        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        if not text_blocks:
            raise RuntimeError("Anthropic returned no text content.")
        return "".join(text_blocks)
