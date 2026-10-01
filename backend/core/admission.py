"""
Provider admission (SCALE-004)

A process-local, non-blocking bound on concurrent OpenAI-mode analyses.

``backend/app.py`` calls ``try_acquire()`` on the event loop *before* the
synchronous analysis body is dispatched to anyio's worker threadpool, and
``release()`` once that dispatch has fully returned. When no slot is free the
request is rejected at once (``capacity_exceeded``); it never waits here and
never waits in the threadpool queue.

Scope and limits
----------------
- Per process. Several uvicorn workers or replicas each get their own budget,
  so aggregate provider concurrency is (processes x capacity).
- No queue, no waiting, no adaptation: capacity is fixed at construction.
- A plain lock-protected counter, deliberately independent of any event loop,
  so it behaves identically under uvicorn, TestClient's per-client loops, and
  plain threads.
"""

from __future__ import annotations

import threading

from backend.core.config import OPENAI_MAX_CONCURRENT_ANALYSES


class ProviderAdmission:
    """A fixed number of slots; ``try_acquire`` never blocks."""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        self._capacity = capacity
        self._in_flight = 0
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def try_acquire(self) -> bool:
        """Take a slot if one is free; return False (without waiting) otherwise."""
        with self._lock:
            if self._in_flight >= self._capacity:
                return False
            self._in_flight += 1
            return True

    def release(self) -> None:
        """Return a slot. Releasing more than was acquired is a bug, not a no-op."""
        with self._lock:
            if self._in_flight <= 0:
                raise RuntimeError("ProviderAdmission released more times than acquired")
            self._in_flight -= 1


# The process-wide budget, built eagerly at import (no I/O, no credential, no
# event-loop binding). Tests substitute their own instance on ``backend.app``.
provider_admission = ProviderAdmission(OPENAI_MAX_CONCURRENT_ANALYSES)
