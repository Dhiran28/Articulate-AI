"""
GeminiProvider (Milestone 5.1): calls Google's Gemini API via the unified
`google-genai` SDK (the Gemini Developer API surface, not Vertex AI).
"""

import logging

from google.genai import Client
from google.genai.errors import APIError
from google.genai.types import GenerateContentConfig, HttpOptions

logger = logging.getLogger(__name__)


class GeminiProvider:
    provider_name = "gemini"
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
        self._client = Client(api_key=api_key) if api_key else None
        self._temperature = temperature
        # google-genai's HttpOptions.timeout is milliseconds, not seconds
        # — converted once here so the rest of this class, and every
        # caller configuring `timeout_seconds`, stays in the same unit
        # every other provider adapter and TimeoutPolicy use.
        self._timeout_ms = int(timeout_seconds * 1000)
        self.last_usage: dict[str, int] | None = None

    async def generate(self, prompt: str) -> str:
        if self._client is None:
            raise RuntimeError("GeminiProvider has no API key configured.")

        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=self._temperature,
                    http_options=HttpOptions(timeout=self._timeout_ms),
                ),
            )
        except APIError:
            logger.exception("Gemini LLM call failed (model=%s)", self.model_name)
            raise

        usage = response.usage_metadata
        self.last_usage = (
            {
                "prompt_tokens": usage.prompt_token_count,
                "completion_tokens": usage.candidates_token_count,
                "total_tokens": usage.total_token_count,
            }
            if usage is not None
            else None
        )

        text = response.text
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text
