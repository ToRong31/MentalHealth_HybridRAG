"""
OpenAIClient — async LLM wrapper via OpenAI-compatible endpoints (NVIDIA, Ollama, vLLM, etc.).

Usage:
    client = OpenAIClient(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
        model="openai/gpt-oss-120b",
    )
    text = await client.generate("Hello", temperature=0.7)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    Async OpenAI-compatible LLM client.

    Supports any server implementing the OpenAI Chat Completions API:
      - NVIDIA API        → base_url="https://integrate.api.nvidia.com/v1"
      - Local Ollama      → base_url="http://localhost:11434/v1"
      - vLLM / TGI        → base_url="http://localhost:8000/v1"
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        default_temperature: float = 0.7,
        default_max_tokens: int = 1024,
        max_retries: int = 3,
        timeout_seconds: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazily init the async OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=self.max_retries,
            )
            logger.info(
                "[OpenAIClient] Connected — base_url=%s model=%s",
                self.base_url,
                self.model,
            )
        return self._client

    # ── Public API ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text from a plain string prompt.

        Signature mirrors GeminiClient.generate() for easy swap.
        """
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=(
                temperature if temperature is not None else self.default_temperature
            ),
            max_tokens=(
                max_tokens if max_tokens is not None else self.default_max_tokens
            ),
            stop=stop,
            stream=False,
            **kwargs,
        )
        content = response.choices[0].message.content or ""
        logger.debug("[OpenAIClient] generate success, %d chars", len(content))
        return content.strip()

    async def generate_structured(
        self,
        prompt: str,
        response_schema: dict[str, Any],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON output matching a response_schema."""
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=(
                    temperature if temperature is not None else self.default_temperature
                ),
                max_tokens=(
                    max_tokens if max_tokens is not None else self.default_max_tokens
                ),
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or "{}"
            return json.loads(raw)
        except json.JSONDecodeError as je:
            logger.warning("[OpenAIClient] JSON parse failed: %s", je)
            return {}
        except Exception as e:
            logger.warning("[OpenAIClient] generate_structured failed: %s", e)
            return {}

    def count_tokens(self, prompt: str) -> int:
        """Approximate token count (~4 chars per token)."""
        return len(prompt) // 4
