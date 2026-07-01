"""Layer 2 – Rate limiter for AKShare / HTTP requests."""
from __future__ import annotations

import asyncio
import time
from collections import deque


class RateLimiter:
    """Token-bucket style rate limiter to avoid IP bans from data sources.

    Parameters
    ----------
    max_calls:
        Maximum number of calls allowed within the time window.
    period:
        Time window in seconds.
    """

    def __init__(self, max_calls: int = 10, period: float = 1.0) -> None:
        self._max_calls = max_calls
        self._period = period
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a call slot is available."""
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps outside the current window
            while self._calls and now - self._calls[0] >= self._period:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                sleep_for = self._period - (now - self._calls[0])
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                # Re-prune after sleep
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self._period:
                    self._calls.popleft()
            self._calls.append(time.monotonic())

    def acquire_sync(self) -> None:
        """Synchronous version for non-async code paths."""
        now = time.monotonic()
        while self._calls and now - self._calls[0] >= self._period:
            self._calls.popleft()
        if len(self._calls) >= self._max_calls:
            sleep_for = self._period - (now - self._calls[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            while self._calls and now - self._calls[0] >= self._period:
                self._calls.popleft()
        self._calls.append(time.monotonic())


# Shared global limiters
akshare_limiter = RateLimiter(max_calls=5, period=1.0)   # AKShare: 5 req/s
http_limiter = RateLimiter(max_calls=3, period=1.0)      # backup HTTP: 3 req/s
