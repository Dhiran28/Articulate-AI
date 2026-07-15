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


class TestDefaultLLMReasonerLogging:
    """
    Milestone 5.1: one consolidated log line per call, covering session
    id, provider, model, prompt id/version, latency, token usage, and
    errors — see reason()'s own docstring in app/llm/reasoner.py for why
    this lives here rather than in each caller (ReasoningPass,
    CoachingEngine).
    """

    async def test_success_log_line_carries_every_required_field(
        self, prompt_registry: PromptRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = FakeProvider(responses=['{"label": "clear", "explanation": "fine"}'])
        provider.last_usage = {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        with caplog.at_level("INFO", logger="app.llm.reasoner"):
            await reasoner.reason(
                "structure_v1", {"transcript": "x", "session_id": "abc-123"}, _ExampleSchema
            )

        [record] = [r for r in caplog.records if r.name == "app.llm.reasoner"]
        message = record.getMessage()
        assert "session_id=abc-123" in message
        assert "provider=fake" in message
        assert "model=fake-model" in message
        assert "prompt_id=structure_v1" in message
        assert "prompt_version=" in message
        assert "latency_ms=" in message
        assert "prompt_tokens=12" in message
        assert "completion_tokens=4" in message
        assert "total_tokens=16" in message
        assert "status=ok" in message

    async def test_missing_session_id_logs_unknown_rather_than_failing(
        self, prompt_registry: PromptRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = FakeProvider(responses=['{"label": "clear", "explanation": "fine"}'])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        with caplog.at_level("INFO", logger="app.llm.reasoner"):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

        [record] = [r for r in caplog.records if r.name == "app.llm.reasoner"]
        assert "session_id=unknown" in record.getMessage()

    async def test_a_provider_with_no_last_usage_attribute_logs_na(
        self, prompt_registry: PromptRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        # FakeProvider (this file) never sets last_usage — the same shape
        # a hand-written test double for LLMReasoner-adjacent tests
        # elsewhere in this suite has. Logging must not assume every
        # provider carries the (optional, non-Protocol) attribute.
        provider = FakeProvider(responses=['{"label": "clear", "explanation": "fine"}'])
        reasoner = DefaultLLMReasoner(provider, prompt_registry)

        with caplog.at_level("INFO", logger="app.llm.reasoner"):
            await reasoner.reason("structure_v1", {"transcript": "x"}, _ExampleSchema)

        [record] = [r for r in caplog.records if r.name == "app.llm.reasoner"]
        assert "prompt_tokens=n/a" in record.getMessage()

    async def test_failure_is_logged_at_error_level_with_reason(
        self, prompt_registry: PromptRegistry, caplog: pytest.LogCaptureFixture
    ) -> None:
        provider = FakeProvider(error=RuntimeError("boom"))
        reasoner = DefaultLLMReasoner(provider, prompt_registry, retry_policy=RetryPolicy(max_attempts=1))

        with caplog.at_level("INFO", logger="app.llm.reasoner"):
            with pytest.raises(LLMProviderError):
                await reasoner.reason(
                    "structure_v1", {"transcript": "x", "session_id": "abc-123"}, _ExampleSchema
                )

        [record] = [r for r in caplog.records if r.name == "app.llm.reasoner"]
        assert record.levelname == "ERROR"
        message = record.getMessage()
        assert "session_id=abc-123" in message
        assert "status=error" in message
        assert "reason=llm_provider_error" in message


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
