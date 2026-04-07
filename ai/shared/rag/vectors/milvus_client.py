"""
MilvusClient — vector search wrapper.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_connected: bool = False
_col: Any = None


class MilvusClient:
    """
    Milvus vector database client.

    Usage:
        client = MilvusClient(uri="http://localhost:19530", collection="mental_health")
        results = client.search(query_vector, top_k=5)
    """

    def __init__(
        self,
        uri: str = "http://localhost:19530",
        collection: str = "mental_health",
        db: str = "default",
        token: str = "",
        hnsw_ef: int = 128,
    ):
        self.uri = uri
        self.collection_name = collection
        self.db = db
        self.token = token
        self.hnsw_ef = hnsw_ef
        self._connected = False
        self._col: Optional[Any] = None

    # ── Connection ─────────────────────────────────────────────────────────

    def _ensure_connection(self) -> None:
        """Lazy connect to Milvus."""
        global _connected, _col
        if _connected and _col is not None:
            self._col = _col
            self._connected = True
            return

        try:
            from pymilvus import connections, Collection, utility

            params: dict[str, Any] = {
                "alias": "default",
                "uri": self.uri,
                "db_name": self.db,
            }
            if self.token and self.token.strip():
                params["token"] = self.token
                params["secure"] = True
            else:
                params["secure"] = False

            connections.connect(**params)

            if self.collection_name not in utility.list_collections():
                logger.warning(
                    "[MilvusClient] Collection '%s' not found. Run ingestion pipeline first.",
                    self.collection_name,
                )
                self._connected = True
                self._col = None
                return

            self._col = Collection(self.collection_name)
            self._col.load()
            _col = self._col
            _connected = True
            self._connected = True
            logger.info(
                "[MilvusClient] Connected, collection: %s", self.collection_name
            )

        except ImportError:
            logger.warning("[MilvusClient] pymilvus not installed")
            self._connected = True
            self._col = None
        except Exception as e:
            logger.warning("[MilvusClient] Connection failed: %s", e)
            self._connected = True
            self._col = None

    # ── Search ────────────────────────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search Milvus vector index.

        Returns:
            [{"node_id": int, "score": float}, ...]
        """
        self._ensure_connection()

        if self._col is None:
            logger.debug("[MilvusClient] No collection — returning empty")
            return []

        try:
            res = self._col.search(
                data=[query_vector],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"ef": self.hnsw_ef}},
                limit=top_k,
                output_fields=[],
            )

            hits = res[0]
            results = []
            for h in hits:
                score = float(h.distance)
                if score >= threshold:
                    results.append({"node_id": h.id, "score": score})

            logger.debug("[MilvusClient] search returned %d hits", len(results))
            return results

        except Exception as e:
            logger.warning("[MilvusClient] search failed: %s", e)
            return []

    # ── Insert ───────────────────────────────────────────────────────────

    def insert(
        self,
        vectors: list[list[float]],
        ids: Optional[list[int]] = None,
    ) -> list[int]:
        """Insert vectors into collection. Returns inserted IDs."""
        self._ensure_connection()

        if self._col is None:
            logger.warning("[MilvusClient] No collection to insert into")
            return []

        try:
            data = [{"embedding": v} for v in vectors]
            result = self._col.insert(data)
            self._col.flush()
            logger.info("[MilvusClient] Inserted %d vectors", len(vectors))
            return result.primary_keys

        except Exception as e:
            logger.warning("[MilvusClient] insert failed: %s", e)
            return []

    # ── Delete ───────────────────────────────────────────────────────────

    def delete(self, ids: list[int]) -> None:
        """Delete vectors by ID."""
        self._ensure_connection()
        if self._col is None:
            return

        try:
            expr = f"id in {ids}"
            self._col.delete(expr)
            self._col.flush()
            logger.info("[MilvusClient] Deleted %d vectors", len(ids))
        except Exception as e:
            logger.warning("[MilvusClient] delete failed: %s", e)

    def close(self) -> None:
        """Close Milvus connection."""
        global _connected, _col
        _connected = False
        _col = None
        self._col = None
        try:
            from pymilvus import connections

            connections.disconnect("default")
        except Exception:
            pass
