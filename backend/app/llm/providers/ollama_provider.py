"""
OllamaProvider (Milestone 5.1): calls a local (or self-hosted) Ollama
server's REST API directly over HTTP, rather than adding the separate
`ollama` PyPI package as a dependency for what is a small, stable JSON
API (`POST /api/generate`) — the same "don't add a whole SDK for one
HTTP call" reasoning this codebase hasn't had occasion to state before
now, since every other vendor here has a real client SDK worth using.

No API key: a local Ollama install has none by default, and
`Settings.llm_api_key_for("ollama")` returns `None` on purpose (see
app/core/config.py). What varies per deployment is `ollama_base_url`
instead.
"""

import logging

import httpx

logger = logging.getLogger(__name__)


class OllamaProvider:
    provider_name = "ollama"
    version = "1.0.0"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        temperature: float = 0.3,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.model_name = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds
        self.last_usage: dict[str, int] | None = None

    async def generate(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": self._temperature},
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(
                "Ollama LLM call failed (model=%s, base_url=%s)", self.model_name, self._base_url
            )
            raise

        payload = response.json()

        prompt_tokens = payload.get("prompt_eval_count")
        completion_tokens = payload.get("eval_count")
        self.last_usage = (
            {
                "prompt_tokens": prompt_tokens or 0,
                "completion_tokens": completion_tokens or 0,
                "total_tokens": (prompt_tokens or 0) + (completion_tokens or 0),
            }
            if prompt_tokens is not None or completion_tokens is not None
            else None
        )

        text = payload.get("response")
        if not text:
            raise RuntimeError("Ollama returned an empty response.")
        return text
