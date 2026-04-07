"""
Neo4jClient — graph database wrapper.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_driver: Any = None


class Neo4jClient:
    """
    Neo4j graph database client.

    Usage:
        client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="...")
        subgraph = await client.expand_subgraph([1, 2, 3])
        names = await client.get_node_names([1, 2])
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver: Optional[Any] = None

    def _ensure_driver(self) -> Any:
        """Lazy connect to Neo4j."""
        global _driver
        if _driver is not None:
            self._driver = _driver
            return _driver

        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            _driver = self._driver
            logger.info("[Neo4jClient] Connected to %s", self.uri)
            return self._driver
        except ImportError:
            logger.warning("[Neo4jClient] neo4j package not installed")
            return None
        except Exception as e:
            logger.warning("[Neo4jClient] Connection failed: %s", e)
            return None

    # ── Graph expansion ───────────────────────────────────────────────────────

    def expand_subgraph(
        self,
        anchor_ids: list[int],
        max_level: int = 2,
        limit: int = 10,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Expand from anchor node IDs using APOC path expansion.

        Returns (nodes, relationships):
        - nodes: list of node dicts with id, labels, properties
        - relationships: list of rel dicts
        """
        driver = self._ensure_driver()
        if driver is None:
            return [], []

        if not anchor_ids:
            return [], []

        rel_filter = (
            "TARGETS>|ALLEVIATES>|WORSENED_BY>|TRIGGERED_BY>|"
            "HAS_FREQUENCY>|HAS_DURATION>|HAS_SEVERITY>|OCCURRED_AT>|"
            "NEGATES>|RELATED_TO>|"
            "TARGETS<|ALLEVIATES<|WORSENED_BY<|TRIGGERED_BY<|"
            "HAS_FREQUENCY<|HAS_DURATION<|HAS_SEVERITY<|OCCURRED_AT<|"
            "NEGATES<|RELATED_TO<"
        )

        cypher = f"""
        MATCH (a:Entity) WHERE a.id IN $ids
        CALL apoc.path.expandConfig(a, {{
            relationshipFilter: "{rel_filter}",
            maxLevel: {max_level},
            bfs: true,
            limit: {limit},
            uniqueness: "NODE_GLOBAL"
        }}) YIELD path

        WITH collect(DISTINCT a) AS anchors,
             collect(DISTINCT path) AS paths

        WITH
            apoc.coll.toSet(anchors) +
            apoc.coll.toSet([n IN apoc.coll.flatten([p IN paths | nodes(p)]) | n]) AS raw_nodes,
            apoc.coll.toSet([r IN apoc.coll.flatten([p IN paths | relationships(p)]) | r]) AS raw_rels

        RETURN raw_nodes, raw_rels
        """

        try:
            with driver.session() as session:
                rec = session.run(cypher, {"ids": anchor_ids}).single()
                if not rec:
                    return [], []

                raw_nodes = rec["raw_nodes"]
                raw_rels = rec["raw_rels"]

                nodes = []
                for n in raw_nodes:
                    nodes.append(
                        {
                            "id": n.get("id"),
                            "labels": list(n.labels),
                            "name": n.get("name", ""),
                            "type": n.get("type", ""),
                            "description": n.get("description", ""),
                        }
                    )

                rels = []
                for r in raw_rels:
                    rels.append(
                        {
                            "type": r.type,
                            "start_node": r.start_node.get("id"),
                            "end_node": r.end_node.get("id"),
                        }
                    )

                logger.info(
                    "[Neo4jClient] expand_subgraph: %d nodes, %d rels",
                    len(nodes),
                    len(rels),
                )
                return nodes, rels

        except Exception as e:
            logger.warning("[Neo4jClient] expand_subgraph failed: %s", e)
            return [], []

    # ── Node names ─────────────────────────────────────────────────────────────

    def get_node_names(self, node_ids: list[int]) -> dict[int, str]:
        """
        Get node names from IDs.

        Returns: {node_id: name, ...}
        """
        driver = self._ensure_driver()
        if driver is None:
            return {}

        if not node_ids:
            return {}

        query = """
        MATCH (n:Entity) WHERE n.id IN $ids
        RETURN n.id AS node_id, n.name AS name
        """

        try:
            with driver.session() as session:
                result = session.run(query, {"ids": node_ids})
                node_map = {}
                for record in result:
                    nid = record["node_id"]
                    name = record["name"] or f"Node_{nid}"
                    node_map[nid] = name

                # Fill in missing
                for nid in node_ids:
                    if nid not in node_map:
                        node_map[nid] = f"Node_{nid}"

                return node_map

        except Exception as e:
            logger.warning("[Neo4jClient] get_node_names failed: %s", e)
            return {}

    # ── Simple query ─────────────────────────────────────────────────────────────

    def run_query(
        self, cypher: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a raw Cypher query. Returns list of result dicts."""
        driver = self._ensure_driver()
        if driver is None:
            return []

        try:
            with driver.session() as session:
                result = session.run(cypher, params or {})
                return [dict(record) for record in result]

        except Exception as e:
            logger.warning("[Neo4jClient] run_query failed: %s", e)
            return []

    def close(self) -> None:
        """Close the driver."""
        global _driver
        if self._driver:
            self._driver.close()
        _driver = None
        self._driver = None
