"""
TimeoutPolicy (Sprint 4.4): wraps a call with a hard time limit so a
hung provider request can never hold up a caller indefinitely — the gap
ADR 003 §6 flagged ("no explicit timeout configured on the AsyncOpenAI
client") is exactly what this exists to close, generically, for any
future provider.
"""

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

from .errors import LLMTimeoutError

T = TypeVar("T")


@dataclass
class TimeoutPolicy:
    timeout_seconds: float = 30.0

    async def run(self, fn: Callable[[], Awaitable[T]]) -> T:
        try:
            return await asyncio.wait_for(fn(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise LLMTimeoutError(
                f"The provider call did not complete within {self.timeout_seconds}s.",
            ) from exc
