"""
Tests for DefaultLLMReasoner (Sprint 4.4) — the full pipeline: prompt
lookup, rendering, provider call (timeout + retry wrapped), JSON
parsing, schema validation.

No real API is called anywhere in this file — FakeProvider is a plain
in-memory stand-in satisfying the LLMProvider Protocol, the same
approach test_transcription.py uses for TranscriptionProvider.

See tests/README.md for how this file fits into the overall suite.
"""

from pathlib import Path

import pytest
from pydantic import BaseModel

from app.llm.errors import (
    LLMInvalidResponseError,
    LLMProviderError,
    LLMSchemaError,
    LLMTimeoutError,
    NoProviderConfiguredError,
    PromptNotFoundError,
)
from app.llm.prompt_registry import PromptRegistry
from app.llm.provider import LLMProvider
from app.llm.reasoner import DefaultLLMReasoner
from app.llm.retry_policy import RetryPolicy
from app.llm.timeout_policy import TimeoutPolicy

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "prompts"


class _ExampleSchema(BaseModel):
    label: str
    explanation: str


class FakeProvider:
    """
    Returns whatever canned response(s) it's constructed with, one per
    call, and records every prompt it was actually sent — so a test can
    both control what "the LLM said" and verify what was asked.
    """

    provider_name = "fake"
    model_name = "fake-model"
    version = "0.0.1-test"

    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self._responses = list(responses or [])
        self._error = error
        self.prompts_received: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)


class SlowProvider:
    provider_name = "slow"
    model_name = "slow-model"
    version = "0.0.1-test"

    async def generate(self, prompt: str) -> str:
        import asyncio

        await asyncio.sleep(1)
        return "{}"


@pytest.fixture
def prompt_registry() -> PromptRegistry:
    registry = PromptRegistry()
    registry.discover_directory(FIXTURES_DIR)
    return registry


class TestProviderProtocolConformance:
    def test_fake_provider_satisfies_llm_provider(self) -> None:
        assert isinstance(FakeProvider(), LLMProvider)


class TestDefaultLLMReasonerHappyPath:
    async def test_returns_a_validated_schema_instance(self, prompt_registry: PromptRegistry) -> None:
        provider = FakeProvider(responses=['{"label": "clear", "explanation": "well organized"}'])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        result = await reasoner.reason(
            "structure_v1", {"transcript": "we should ship it"}, _ExampleSchema
        )

        assert isinstance(result, _ExampleSchema)
        assert result.label == "clear"

    async def test_the_rendered_prompt_reaches_the_provider(self, prompt_registry: PromptRegistry) -> None:
        provider = FakeProvider(responses=['{"label": "clear", "explanation": "fine"}'])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        await reasoner.reason("structure_v1", {"transcript": "hello world"}, _ExampleSchema)

        assert "hello world" in provider.prompts_received[0]

    async def test_strips_a_code_fence_from_the_providers_response(self, prompt_registry: PromptRegistry) -> None:
        provider = FakeProvider(responses=['```json\n{"label": "clear", "explanation": "fine"}\n```'])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        result = await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)
        assert result.label == "clear"


class TestDefaultLLMReasonerFailureModes:
    async def test_unknown_prompt_id_raises_prompt_not_found(self, prompt_registry: PromptRegistry) -> None:
        reasoner = DefaultLLMReasoner(FakeProvider(), prompt_registry)

        with pytest.raises(PromptNotFoundError):
            await reasoner.reason("does_not_exist", {"transcript": "x"}, _ExampleSchema)

    async def test_missing_template_variable_propagates_as_value_error(
        self, prompt_registry: PromptRegistry
    ) -> None:
        reasoner = DefaultLLMReasoner(FakeProvider(), prompt_registry)

        with pytest.raises(ValueError):
            await reasoner.reason("structure_v1", {}, _ExampleSchema)  # missing $transcript

    async def test_malformed_json_raises_llm_invalid_response_error(
        self, prompt_registry: PromptRegistry
    ) -> None:
        provider = FakeProvider(responses=["not json at all"])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        with pytest.raises(LLMInvalidResponseError):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

    async def test_schema_mismatch_raises_llm_schema_error(self, prompt_registry: PromptRegistry) -> None:
        provider = FakeProvider(responses=['{"label": "clear"}'])  # missing "explanation"
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        with pytest.raises(LLMSchemaError):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

    async def test_provider_error_propagates_as_llm_provider_error_after_retries(
        self, prompt_registry: PromptRegistry
    ) -> None:
        provider = FakeProvider(error=RuntimeError("connection reset"))
        reasoner = DefaultLLMReasoner(
            provider,
            prompt_registry,
            retry_policy=RetryPolicy(max_attempts=2, sleep=_instant_sleep),
        )

        with pytest.raises(LLMProviderError):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

        assert len(provider.prompts_received) == 2  # retried once, per max_attempts=2

    async def test_provider_error_retried_then_succeeds(self, prompt_registry: PromptRegistry) -> None:
        provider = _FlakyThenOkProvider(fail_times=1, ok_response='{"label": "clear", "explanation": "fine"}')
        reasoner = DefaultLLMReasoner(
            provider,
            prompt_registry,
            retry_policy=RetryPolicy(max_attempts=3, sleep=_instant_sleep),
        )

        result = await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

        assert result.label == "clear"
        assert provider.call_count == 2

    async def test_timeout_raises_llm_timeout_error(self, prompt_registry: PromptRegistry) -> None:
        reasoner = DefaultLLMReasoner(
            SlowProvider(),
            prompt_registry,
            timeout_policy=TimeoutPolicy(timeout_seconds=0.01),
            retry_policy=RetryPolicy(max_attempts=1),
        )

        with pytest.raises(LLMTimeoutError):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

    def test_no_provider_raises_no_provider_configured(self, prompt_registry: PromptRegistry) -> None:
        with pytest.raises(NoProviderConfiguredError):
            DefaultLLMReasoner(None, prompt_registry)


async def _instant_sleep(_seconds: float) -> None:
    return None


class _FlakyThenOkProvider:
    provider_name = "flaky"
    model_name = "flaky-model"
    version = "0.0.1-test"

    def __init__(self, fail_times: int, ok_response: str) -> None:
        self._fail_times = fail_times
        self._ok_response = ok_response
        self.call_count = 0

    async def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise RuntimeError("temporary blip")
        return self._ok_response
