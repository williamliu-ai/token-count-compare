# Controlled code-review fixture: async cache refresh and a small worker.
# This file contains plausible Python with subtle edge cases. It is meant
# for code-review style reading by a model, not for execution.
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import Generic, TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float
    fetch_count: int = 0


class TokenCache(Generic[T]):
    """Single-key in-memory async cache with double-checked locking.

    The cache holds at most one value at a time. It is intended for short-lived
    secrets such as API tokens, where a stale read is acceptable for a few
    hundred milliseconds but a thundering herd of refresh calls is not.
    """

    def __init__(
        self,
        fetcher: Callable[[], Awaitable[T]],
        ttl_seconds: float = 30.0,
        soft_ttl_ratio: float = 0.8,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if not 0 < soft_ttl_ratio <= 1:
            raise ValueError("soft_ttl_ratio must be in (0, 1]")
        self._fetcher = fetcher
        self.ttl_seconds = ttl_seconds
        self.soft_ttl_ratio = soft_ttl_ratio
        self._entry: CacheEntry[T] | None = None
        self._lock = asyncio.Lock()
        self._refresh_task: asyncio.Task[None] | None = None

    @property
    def soft_expiry(self) -> float:
        return self.ttl_seconds * self.soft_ttl_ratio

    async def get(self) -> T:
        now = monotonic()
        entry = self._entry
        if entry and entry.expires_at > now:
            self._maybe_schedule_refresh(entry, now)
            return entry.value
        async with self._lock:
            entry = self._entry
            if entry and entry.expires_at > monotonic():
                return entry.value
            value = await self._fetch_new_token()
            self._entry = CacheEntry(
                value=value,
                expires_at=monotonic() + self.ttl_seconds,
                fetch_count=(entry.fetch_count + 1) if entry else 1,
            )
            return value

    def _maybe_schedule_refresh(self, entry: CacheEntry[T], now: float) -> None:
        soft_deadline = entry.expires_at - (self.ttl_seconds - self.soft_expiry)
        if now < soft_deadline:
            return
        if self._refresh_task and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.create_task(self._refresh_in_background())

    async def _refresh_in_background(self) -> None:
        try:
            async with self._lock:
                value = await self._fetch_new_token()
                previous = self._entry
                self._entry = CacheEntry(
                    value=value,
                    expires_at=monotonic() + self.ttl_seconds,
                    fetch_count=(previous.fetch_count + 1) if previous else 1,
                )
        except Exception:
            log.exception("background token refresh failed; keeping previous entry")

    async def _fetch_new_token(self) -> T:
        return await self._fetcher()

    def invalidate(self) -> None:
        self._entry = None


class RateLimiter:
    """Simple sliding-window rate limiter, monotonic-clock based.

    Not suitable for distributed use; this is a per-process limiter only.
    """

    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = monotonic()
            cutoff = now - self.window_seconds
            self._events = [t for t in self._events if t >= cutoff]
            if len(self._events) >= self.max_events:
                wait_for = self._events[0] + self.window_seconds - now
                if wait_for > 0:
                    await asyncio.sleep(wait_for)
            self._events.append(monotonic())


async def fetch_token() -> str:
    await asyncio.sleep(0.01)
    return f"token-{int(time.time() * 1000)}"


async def main() -> None:
    cache: TokenCache[str] = TokenCache(fetch_token, ttl_seconds=0.1)
    limiter = RateLimiter(max_events=4, window_seconds=0.5)
    seen: set[str] = set()
    for _ in range(8):
        await limiter.acquire()
        token = await cache.get()
        seen.add(token)
    log.info("distinct tokens observed: %d", len(seen))


if __name__ == "__main__":
    asyncio.run(main())
