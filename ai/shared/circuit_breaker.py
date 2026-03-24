"""
Circuit Breaker pattern implementation.
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
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """
    Circuit Breaker for protecting agent operations.

    States:
      CLOSED  → Normal operation
      OPEN    → Failures exceeded threshold
      HALF_OPEN → Testing recovery
    """

    name: str = "default"
    threshold: int = 5
    timeout: float = 30.0
    half_open_max_calls: int = 1

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.timeout:
                logger.info(f"[CircuitBreaker:{self.name}] OPEN -> HALF_OPEN")
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
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.OPEN:
            return False
        return self._half_open_calls < self.half_open_max_calls

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        if not self.can_execute():
            raise CircuitOpenError(
                f"Circuit breaker '{self.name}' is OPEN",
                agent_id=self.name,
            )

        async with self._lock:
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
                raise RetryableError(
                    str(e),
                    agent_id=self.name,
                    retry_count=self._failure_count,
                    max_retries=self.threshold,
                ) from e

    async def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info(f"[CircuitBreaker:{self.name}] HALF_OPEN -> CLOSED (success)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            if self._failure_count > 0:
                self._failure_count -= 1
        self._success_count += 1

    async def _on_failure(self, error_message: str) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        logger.warning(
            f"[CircuitBreaker:{self.name}] Failure #{self._failure_count}/{self.threshold}: {error_message}"
        )

        if self._failure_count >= self.threshold:
            if self._state != CircuitState.OPEN:
                logger.error(
                    f"[CircuitBreaker:{self.name}] Threshold reached -> OPEN"
                )
            self._state = CircuitState.OPEN
            self._half_open_calls = 0

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        logger.info(f"[CircuitBreaker:{self.name}] Manually reset to CLOSED")

    def get_stats(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "threshold": self.threshold,
            "timeout_seconds": self.timeout,
        }
