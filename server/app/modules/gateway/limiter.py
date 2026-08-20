"""In-process concurrency limiter keyed by (kind, id): user and token levels.

Single-process guarantee only (documented limitation). For multi-worker setups
this must be replaced with a Redis-based counter.
"""

import asyncio
from collections import defaultdict


class ConcurrencyLimiter:
    def __init__(self) -> None:
        self._inflight: dict[tuple, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def acquire(self, key: tuple, limit: int) -> bool:
        """Return True when a slot is acquired, False when `limit` is reached (limit<=0 = unlimited)."""
        if limit <= 0:
            return True
        async with self._lock:
            current = self._inflight[key]
            if current >= limit:
                return False
            self._inflight[key] = current + 1
            return True

    async def release(self, key: tuple, limit: int) -> None:
        # A token acquired with limit<=0 never incremented the counter; skip to avoid underflow.
        if limit > 0:
            await self.release_key(key)

    async def release_key(self, key: tuple) -> None:
        async with self._lock:
            if self._inflight.get(key, 0) > 0:
                self._inflight[key] -= 1


limiter = ConcurrencyLimiter()
