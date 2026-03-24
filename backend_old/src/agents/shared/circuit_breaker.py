"""
Circuit Breaker pattern implementation.
Prevents cascading failures by stopping requests when a service is unhealthy.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar

from .exceptions import CircuitOpenError, RetryableError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"   # Normal operation, requests pass through
    OPEN = "open"       # Failure threshold exceeded, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker for protecting agent operations.

    States:
      CLOSED  → Normal: requests go through, failures increment counter
      OPEN    → Failure threshold reached: requests fail immediately
      HALF_OPEN → After timeout: one test request allowed

    Usage:
        cb = CircuitBreaker(name="diagnostic_retrieval", threshold=5, timeout=30.0)

        async def fetch_diagnostics():
            async with cb:
                return await do_actual_work()

        # Or manually:
        if cb.can_execute():
            result = await cb.call(fetch_diagnostics)
    """

    name: str = "default"
    threshold: int = 5          # Failures before opening circuit
    timeout: float = 30.0       # Seconds before trying HALF_OPEN
    half_open_max_calls: int = 1  # Test calls allowed in HALF_OPEN

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        """Return current state, checking timeout for OPEN → HALF_OPEN transition."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.timeout:
                logger.info(f"[CircuitBreaker:{self.name}] OPEN → HALF_OPEN (timeout elapsed)")
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    @property
    def is_closed(self) -> bool:
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        return self.state == CircuitState.HALF_OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed right now."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        # HALF_OPEN: allow up to half_open_max_calls
        return self._half_open_calls < self.half_open_max_calls

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a coroutine with circuit breaker protection.

        Raises:
            CircuitOpenError: Circuit is OPEN
            RetryableError: Original error (wrapped)
        """
        if not self.can_execute():
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN",
                agent_id=self.name,
            )

        async with self._lock:
            # Double-check after acquiring lock
            if not self.can_execute():
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN",
                    agent_id=self.name,
                )

            try:
                if self._state == CircuitState.HALF_OPEN:
                    self._half_open_calls += 1

                result = await func(*args, **kwargs)
                await self._on_success()
                return result

            except Exception as e:
                await self._on_failure(str(e))
                # Re-raise as RetryableError to indicate it can be retried later
                raise RetryableError(
                    str(e),
                    agent_id=self.name,
                    retry_count=self._failure_count,
                    max_retries=self.threshold,
                ) from e

    # Alias for use as async context manager
    async def __aenter__(self) -> CircuitBreaker:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and issubclass(exc_type, Exception):
            await self._on_failure(str(exc_val))
        else:
            await self._on_success()

    # ── Internal ─────────────────────────────────────────────────────────

    async def _on_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"[CircuitBreaker:{self.name}] HALF_OPEN → CLOSED (success)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success (slow reset)
            if self._failure_count > 0:
                self._failure_count -= 1
                if self._failure_count < 0:
                    self._failure_count = 0
        self._success_count += 1

    async def _on_failure(self, error_message: str) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        logger.warning(
            f"[CircuitBreaker:{self.name}] Failure #{self._failure_count}/{self.threshold}: {error_message}"
        )

        if self._failure_count >= self.threshold:
            if self._state != CircuitState.OPEN:
                logger.error(
                    f"[CircuitBreaker:{self.name}] Threshold reached → OPEN "
                    f"(failures={self._failure_count}, threshold={self.threshold})"
                )
            self._state = CircuitState.OPEN
            self._half_open_calls = 0

    # ── Admin ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def get_stats(self) -> dict[str, Any]:
        """Return circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "threshold": self.threshold,
            "timeout_seconds": self.timeout,
            "last_failure_age_seconds": (
                time.monotonic() - self._last_failure_time
                if self._last_failure_time > 0 else None
            ),
        }
