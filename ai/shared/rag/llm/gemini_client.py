"""
GeminiClient — LLM wrapper with Gemini API.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Gemini LLM client with async support.

    Usage:
        client = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"))
        response = await client.generate("Hello world")
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-1.5-flash",
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.max_retries = max_retries
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Lazy init of the Gemini client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            logger.warning("[GeminiClient] No API key — LLM calls will fail")
            return None

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            self._client = genai
            logger.info("[GeminiClient] Configured with model: %s", self.model)
            return self._client
        except ImportError:
            logger.warning("[GeminiClient] google-generativeai not installed")
            return None
        except Exception as e:
            logger.warning("[GeminiClient] Configure failed: %s", e)
            return None

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate text from prompt using Gemini.

        Returns the response text.
        Raises RuntimeError if all retries fail.
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("GeminiClient not configured — set GEMINI_API_KEY")

        import asyncio

        last_error = None
        for attempt in range(self.max_retries):
            try:
                model = client.GenerativeModel(self.model)
                response = await asyncio.to_thread(
                    lambda: model.generate_content(
                        prompt,
                        generation_config=client.types.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        ),
                    )
                )
                text = response.text.strip()
                logger.debug(
                    "[GeminiClient] generate success (attempt %d)", attempt + 1
                )
                return text

            except Exception as e:
                last_error = e
                logger.warning(
                    "[GeminiClient] Attempt %d/%d failed: %s",
                    attempt + 1,
                    self.max_retries,
                    e,
                )

        raise RuntimeError(
            f"[GeminiClient] All {self.max_retries} retries failed: {last_error}"
        )

    async def generate_structured(
        self,
        prompt: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate structured JSON output matching a schema.
        """
        client = self._get_client()
        if client is None:
            raise RuntimeError("GeminiClient not configured")

        import asyncio

        try:
            model = client.GenerativeModel(
                self.model,
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                },
            )
            response = await asyncio.to_thread(lambda: model.generate_content(prompt))
            import json

            return json.loads(response.text)

        except Exception as e:
            logger.warning("[GeminiClient] generate_structured failed: %s", e)
            return {}

    def count_tokens(self, prompt: str) -> int:
        """Count tokens in prompt (approximate)."""
        # Rough estimate: ~4 chars per token for Vietnamese
        return len(prompt) // 4
