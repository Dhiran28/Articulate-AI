"""
RetryPolicy (Sprint 4.4): bounded retry with backoff for transient
provider failures. "Bounded" is the load-bearing word — no retry loop in
this system is ever unbounded (the same rule ADR 002 §4 set for the
Transcription Service and ADR 003 §7 carried forward for the CIE).
"""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass
class RetryPolicy:
    """
    Retries `run()`'s callable up to `max_attempts` times (so
    `max_attempts=1` means "no retry, try once"), waiting
    `base_delay_seconds * backoff_multiplier ** attempt_index` between
    attempts. Only exceptions matching `retry_on` (passed to `run()`)
    trigger a retry — anything else propagates immediately, since not
    every failure is transient (a schema error retrying won't fix
    itself; a rate limit might).

    `sleep` defaults to `asyncio.sleep` but is overridable — purely so
    tests can inject a fake that records calls instead of actually
    waiting, without needing to patch a stdlib function globally.
    """

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

    async def run(
        self,
        fn: Callable[[], Awaitable[T]],
        *,
        retry_on: tuple[type[BaseException], ...] = (Exception,),
    ) -> T:
        attempt = 0
        delay = self.base_delay_seconds

        while True:
            attempt += 1
            try:
                return await fn()
            except retry_on:
                if attempt >= self.max_attempts:
                    raise
                await self.sleep(delay)
                delay *= self.backoff_multiplier
