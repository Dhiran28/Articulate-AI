"""
Tests for RetryPolicy and TimeoutPolicy (Sprint 4.4).

See tests/README.md for how this file fits into the overall suite.
Every RetryPolicy test below injects a fake `sleep` that records calls
instead of actually waiting, so backoff delays never slow the suite down
— see RetryPolicy's own docstring for why `sleep` is an injectable
constructor parameter in the first place.
"""

import asyncio

import pytest

from app.llm.errors import LLMTimeoutError
from app.llm.retry_policy import RetryPolicy
from app.llm.timeout_policy import TimeoutPolicy


class _RecordingSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class TestRetryPolicy:
    async def test_succeeds_on_the_first_attempt_without_retrying(self) -> None:
        sleep = _RecordingSleep()
        policy = RetryPolicy(max_attempts=3, sleep=sleep)
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            return "ok"

        result = await policy.run(fn)

        assert result == "ok"
        assert calls == 1
        assert sleep.calls == []  # no retry, no delay

    async def test_retries_a_matching_exception_and_eventually_succeeds(self) -> None:
        sleep = _RecordingSleep()
        policy = RetryPolicy(max_attempts=3, base_delay_seconds=1.0, backoff_multiplier=2.0, sleep=sleep)
        attempts = 0

        async def fn():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("transient")
            return "ok"

        result = await policy.run(fn, retry_on=(ValueError,))

        assert result == "ok"
        assert attempts == 3
        assert sleep.calls == [1.0, 2.0]  # two waits, backing off exponentially

    async def test_raises_after_exhausting_max_attempts(self) -> None:
        sleep = _RecordingSleep()
        policy = RetryPolicy(max_attempts=2, sleep=sleep)
        attempts = 0

        async def fn():
            nonlocal attempts
            attempts += 1
            raise ValueError("still broken")

        with pytest.raises(ValueError):
            await policy.run(fn, retry_on=(ValueError,))

        assert attempts == 2

    async def test_does_not_retry_a_non_matching_exception(self) -> None:
        sleep = _RecordingSleep()
        policy = RetryPolicy(max_attempts=5, sleep=sleep)
        attempts = 0

        async def fn():
            nonlocal attempts
            attempts += 1
            raise TypeError("not the retryable kind")

        with pytest.raises(TypeError):
            await policy.run(fn, retry_on=(ValueError,))

        assert attempts == 1
        assert sleep.calls == []

    def test_rejects_a_non_positive_max_attempts(self) -> None:
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)


class TestTimeoutPolicy:
    async def test_returns_the_result_when_within_the_timeout(self) -> None:
        policy = TimeoutPolicy(timeout_seconds=1.0)

        async def fn():
            return "ok"

        assert await policy.run(fn) == "ok"

    async def test_raises_llm_timeout_error_when_exceeded(self) -> None:
        policy = TimeoutPolicy(timeout_seconds=0.01)

        async def fn():
            await asyncio.sleep(1)
            return "too slow"

        with pytest.raises(LLMTimeoutError):
            await policy.run(fn)
