"""
Tests for the four Milestone 5.1 LLMProvider adapters
(app/llm/providers/{openai,anthropic,gemini,ollama}_provider.py), the
provider factory (app/llm/providers/factory.py), and the LLM-related
`Settings` fields (app/core/config.py) that drive provider selection.

No real network call to any vendor happens anywhere in this file:

  - OpenAIProvider / AnthropicProvider / GeminiProvider each get a real
    SDK client instance (built with a fake API key — the SDK never
    validates a key at construction time), with only the one method that
    would make a network call monkeypatched to return a canned response
    — the exact "monkeypatch the network-calling method, let everything
    else run for real" approach test_transcription.py already uses for
    OpenAIWhisperProvider.
  - OllamaProvider talks to a local REST API over plain httpx, so its
    tests monkeypatch `httpx.AsyncClient.post` instead of an SDK method.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from anthropic import AnthropicError
from google.genai.errors import ClientError
from openai import OpenAIError

from app.core.config import Settings
from app.llm.provider import LLMProvider
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.factory import DEFAULT_MODELS, UnknownProviderError, build_provider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.openai_provider import OpenAIProvider


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "llm_provider": "",
        "llm_model": "",
        "openai_api_key": None,
        "anthropic_api_key": None,
        "google_api_key": None,
        "ollama_base_url": "http://localhost:11434",
        "llm_temperature": 0.3,
        "llm_timeout_seconds": 30.0,
        "llm_max_retries": 3,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSettingsLLMConfig:
    """Settings' LLM fields (Milestone 5.1) — every value env-driven, nothing hardcoded."""

    def test_llm_provider_defaults_to_empty_string(self) -> None:
        assert _settings().llm_provider == ""

    def test_reads_llm_provider_and_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
        settings = Settings()
        assert settings.llm_provider == "anthropic"
        assert settings.llm_model == "claude-sonnet-5"

    def test_reads_temperature_timeout_and_retries_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
        monkeypatch.setenv("LLM_MAX_RETRIES", "5")
        settings = Settings()
        assert settings.llm_temperature == 0.7
        assert settings.llm_timeout_seconds == 45.0
        assert settings.llm_max_retries == 5

    def test_llm_api_key_for_maps_each_vendor_to_its_own_field(self) -> None:
        settings = _settings(openai_api_key="sk-openai", anthropic_api_key="sk-ant", google_api_key="sk-google")
        assert settings.llm_api_key_for("openai") == "sk-openai"
        assert settings.llm_api_key_for("anthropic") == "sk-ant"
        assert settings.llm_api_key_for("gemini") == "sk-google"

    def test_llm_api_key_for_ollama_is_always_none(self) -> None:
        settings = _settings(openai_api_key="sk-openai")
        assert settings.llm_api_key_for("ollama") is None

    def test_llm_api_key_for_unknown_provider_is_none(self) -> None:
        assert _settings().llm_api_key_for("not-a-real-vendor") is None


class TestProviderProtocolConformance:
    def test_every_adapter_satisfies_llm_provider(self) -> None:
        assert isinstance(OpenAIProvider("sk-fake", "gpt-4o-mini"), LLMProvider)
        assert isinstance(AnthropicProvider("sk-fake", "claude-sonnet-5"), LLMProvider)
        assert isinstance(GeminiProvider("fake-key", "gemini-2.0-flash"), LLMProvider)
        assert isinstance(OllamaProvider("http://localhost:11434", "llama3.1"), LLMProvider)


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int, total_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class _FakeMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.message = _FakeMessage(content)


class _FakeChatCompletion:
    def __init__(self, content: str | None, usage: _FakeUsage | None) -> None:
        self.choices = [_FakeChoice(content)]
        self.usage = usage


class TestOpenAIProvider:
    @pytest.fixture
    def provider(self) -> OpenAIProvider:
        return OpenAIProvider("sk-test-fake-key", "gpt-4o-mini", temperature=0.2, timeout_seconds=5.0)

    async def test_returns_the_response_text_and_captures_usage(
        self, provider: OpenAIProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_response = _FakeChatCompletion("hello world", _FakeUsage(10, 5, 15))

        async def fake_create(**kwargs: Any) -> _FakeChatCompletion:
            assert kwargs["model"] == "gpt-4o-mini"
            assert kwargs["temperature"] == 0.2
            assert kwargs["messages"] == [{"role": "user", "content": "say hi"}]
            return fake_response

        monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)

        result = await provider.generate("say hi")

        assert result == "hello world"
        assert provider.last_usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    async def test_no_api_key_raises_before_any_call(self) -> None:
        provider = OpenAIProvider(None, "gpt-4o-mini")
        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_empty_content_raises(self, provider: OpenAIProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_create(**kwargs: Any) -> _FakeChatCompletion:
            return _FakeChatCompletion(None, None)

        monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)

        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_sdk_error_propagates(self, provider: OpenAIProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_create(**kwargs: Any) -> _FakeChatCompletion:
            raise OpenAIError("connection reset")

        monkeypatch.setattr(provider._client.chat.completions, "create", fake_create)

        with pytest.raises(OpenAIError):
            await provider.generate("hi")


class _FakeAnthropicUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeAnthropicMessage:
    def __init__(self, content: list[_FakeTextBlock], usage: _FakeAnthropicUsage) -> None:
        self.content = content
        self.usage = usage


class TestAnthropicProvider:
    @pytest.fixture
    def provider(self) -> AnthropicProvider:
        return AnthropicProvider("sk-ant-fake", "claude-sonnet-5", temperature=0.2, timeout_seconds=5.0)

    async def test_returns_the_response_text_and_captures_usage(
        self, provider: AnthropicProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_response = _FakeAnthropicMessage([_FakeTextBlock("hello there")], _FakeAnthropicUsage(20, 8))

        async def fake_create(**kwargs: Any) -> _FakeAnthropicMessage:
            assert kwargs["model"] == "claude-sonnet-5"
            assert kwargs["temperature"] == 0.2
            assert kwargs["messages"] == [{"role": "user", "content": "say hi"}]
            return fake_response

        monkeypatch.setattr(provider._client.messages, "create", fake_create)

        result = await provider.generate("say hi")

        assert result == "hello there"
        assert provider.last_usage == {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}

    async def test_no_api_key_raises_before_any_call(self) -> None:
        provider = AnthropicProvider(None, "claude-sonnet-5")
        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_no_text_blocks_raises(self, provider: AnthropicProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_create(**kwargs: Any) -> _FakeAnthropicMessage:
            return _FakeAnthropicMessage([], _FakeAnthropicUsage(5, 0))

        monkeypatch.setattr(provider._client.messages, "create", fake_create)

        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_sdk_error_propagates(self, provider: AnthropicProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_create(**kwargs: Any) -> _FakeAnthropicMessage:
            raise AnthropicError("rate limited")

        monkeypatch.setattr(provider._client.messages, "create", fake_create)

        with pytest.raises(AnthropicError):
            await provider.generate("hi")


class _FakeGeminiUsage:
    def __init__(self, prompt_token_count: int, candidates_token_count: int, total_token_count: int) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.total_token_count = total_token_count


class _FakeGeminiResponse:
    def __init__(self, text: str | None, usage_metadata: _FakeGeminiUsage | None) -> None:
        self.text = text
        self.usage_metadata = usage_metadata


class TestGeminiProvider:
    @pytest.fixture
    def provider(self) -> GeminiProvider:
        return GeminiProvider("fake-google-key", "gemini-2.0-flash", temperature=0.2, timeout_seconds=5.0)

    async def test_returns_the_response_text_and_captures_usage(
        self, provider: GeminiProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_response = _FakeGeminiResponse("hello from gemini", _FakeGeminiUsage(11, 6, 17))

        async def fake_generate_content(**kwargs: Any) -> _FakeGeminiResponse:
            assert kwargs["model"] == "gemini-2.0-flash"
            assert kwargs["contents"] == "say hi"
            return fake_response

        monkeypatch.setattr(provider._client.aio.models, "generate_content", fake_generate_content)

        result = await provider.generate("say hi")

        assert result == "hello from gemini"
        assert provider.last_usage == {"prompt_tokens": 11, "completion_tokens": 6, "total_tokens": 17}

    async def test_no_api_key_raises_before_any_call(self) -> None:
        provider = GeminiProvider(None, "gemini-2.0-flash")
        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_empty_text_raises(self, provider: GeminiProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_generate_content(**kwargs: Any) -> _FakeGeminiResponse:
            return _FakeGeminiResponse(None, None)

        monkeypatch.setattr(provider._client.aio.models, "generate_content", fake_generate_content)

        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_sdk_error_propagates(self, provider: GeminiProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_generate_content(**kwargs: Any) -> _FakeGeminiResponse:
            raise ClientError(400, {"error": {"message": "bad request"}})

        monkeypatch.setattr(provider._client.aio.models, "generate_content", fake_generate_content)

        with pytest.raises(ClientError):
            await provider.generate("hi")


class _FakeOllamaResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=httpx.Request("POST", "http://x"), response=None)  # type: ignore[arg-type]


class TestOllamaProvider:
    @pytest.fixture
    def provider(self) -> OllamaProvider:
        return OllamaProvider("http://localhost:11434", "llama3.1", temperature=0.2, timeout_seconds=5.0)

    async def test_returns_the_response_text_and_captures_usage(
        self, provider: OllamaProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any]) -> _FakeOllamaResponse:
            assert url == "http://localhost:11434/api/generate"
            assert json["model"] == "llama3.1"
            assert json["prompt"] == "say hi"
            return _FakeOllamaResponse({"response": "hello from ollama", "prompt_eval_count": 9, "eval_count": 3})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        result = await provider.generate("say hi")

        assert result == "hello from ollama"
        assert provider.last_usage == {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12}

    async def test_strips_trailing_slash_from_base_url(self) -> None:
        provider = OllamaProvider("http://localhost:11434/", "llama3.1")
        assert provider._base_url == "http://localhost:11434"

    async def test_empty_response_text_raises(self, provider: OllamaProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any]) -> _FakeOllamaResponse:
            return _FakeOllamaResponse({"response": ""})

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(RuntimeError):
            await provider.generate("hi")

    async def test_http_error_propagates(self, provider: OllamaProvider, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_post(self: httpx.AsyncClient, url: str, json: dict[str, Any]) -> _FakeOllamaResponse:
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

        with pytest.raises(httpx.HTTPError):
            await provider.generate("hi")


class TestBuildProviderFactory:
    def test_no_provider_configured_returns_none(self) -> None:
        assert build_provider(_settings(llm_provider="")) is None

    def test_unrecognized_provider_raises(self) -> None:
        with pytest.raises(UnknownProviderError):
            build_provider(_settings(llm_provider="watson"))

    def test_selected_provider_missing_credential_returns_none(self) -> None:
        assert build_provider(_settings(llm_provider="anthropic", anthropic_api_key=None)) is None

    @pytest.mark.parametrize(
        "provider_name,api_key_field,adapter_type",
        [
            ("openai", "openai_api_key", OpenAIProvider),
            ("anthropic", "anthropic_api_key", AnthropicProvider),
            ("gemini", "google_api_key", GeminiProvider),
        ],
    )
    def test_builds_the_right_adapter_when_credential_is_present(
        self, provider_name: str, api_key_field: str, adapter_type: type
    ) -> None:
        settings = _settings(llm_provider=provider_name, **{api_key_field: "fake-key"})
        provider = build_provider(settings)
        assert isinstance(provider, adapter_type)
        assert provider.model_name == DEFAULT_MODELS[provider_name]

    def test_ollama_needs_no_credential(self) -> None:
        provider = build_provider(_settings(llm_provider="ollama"))
        assert isinstance(provider, OllamaProvider)
        assert provider.model_name == DEFAULT_MODELS["ollama"]

    def test_explicit_llm_model_overrides_the_default(self) -> None:
        settings = _settings(llm_provider="openai", openai_api_key="fake-key", llm_model="gpt-5")
        provider = build_provider(settings)
        assert provider.model_name == "gpt-5"

    def test_temperature_and_timeout_flow_through_to_the_adapter(self) -> None:
        settings = _settings(
            llm_provider="openai", openai_api_key="fake-key", llm_temperature=0.9, llm_timeout_seconds=12.0
        )
        provider = build_provider(settings)
        assert provider._temperature == 0.9
        assert provider._timeout_seconds == 12.0

    def test_provider_name_is_case_and_whitespace_insensitive(self) -> None:
        settings = _settings(llm_provider="  OpenAI  ", openai_api_key="fake-key")
        provider = build_provider(settings)
        assert isinstance(provider, OpenAIProvider)
