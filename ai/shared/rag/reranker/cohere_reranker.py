"""
CohereReranker — semantic reranking with Cohere API.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CohereReranker:
    """
    Cohere reranker for semantic search result re-ranking.

    Usage:
        reranker = CohereReranker(api_key=os.getenv("COHERE_API_KEY"))
        reranked = reranker.rerank(query="stress", candidates=[...], top_k=5)
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "rerank-multilingual-v3.0",
        top_n: int = 5,
    ):
        self.api_key = api_key or os.getenv("COHERE_API_KEY", "")
        self.model = model
        self.top_n = top_n
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Lazy init of Cohere client."""
        if self._client is not None:
            return self._client

        if not self.api_key:
            logger.warning("[CohereReranker] No API key — reranking disabled")
            return None

        try:
            import cohere

            self._client = cohere.Client(self.api_key)
            logger.info("[CohereReranker] Client initialized")
            return self._client
        except ImportError:
            logger.warning("[CohereReranker] cohere package not installed")
            return None
        except Exception as e:
            logger.warning("[CohereReranker] Init failed: %s", e)
            return None

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
        candidates_key: str = "text",
    ) -> list[dict[str, Any]]:
        """
        Re-rank candidates by semantic relevance to query.

        Parameters
        ----------
        query : str
            The search query.
        candidates : list[dict]
            List of candidate items. Each item should have a text field
            identified by candidates_key.
        top_k : int
            Max reranked results to return.
        candidates_key : str
            Dict key containing the text to rerank.

        Returns
        -------
        list[dict]
            Candidates re-ranked with added "relevance_score" field.
            Sorted by relevance descending.
        """
        client = self._get_client()
        if client is None:
            # No-op: return candidates as-is
            return candidates[:top_k]

        if not candidates:
            return []

        try:
            # Build texts list
            texts = [c.get(candidates_key, str(c)) for c in candidates]

            response = client.rerank(
                query=query,
                documents=texts,
                model=self.model,
                top_n=min(top_k, len(texts)),
                return_documents=False,
            )

            # Map results back to original candidates
            results = []
            for hit in response.results:
                original_idx = hit.index
                results.append(
                    {
                        **candidates[original_idx],
                        "relevance_score": hit.relevance_score,
                    }
                )

            logger.debug(
                "[CohereReranker] reranked %d candidates to %d results",
                len(candidates),
                len(results),
            )
            return results

        except Exception as e:
            logger.warning("[CohereReranker] rerank failed: %s", e)
            return candidates[:top_k]
