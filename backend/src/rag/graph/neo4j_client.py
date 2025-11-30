from typing import List, Dict, Any

from neo4j import GraphDatabase

from src.rag.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_node_names_from_neo4j(node_ids: List[int]) -> Dict[int, str]:
    if not node_ids:
        return {}

    query = """
    MATCH (n:Entity) WHERE n.id IN $ids
    RETURN n.id AS node_id, n.name AS name
    """

    with driver.session() as session:
        result = session.run(query, {"ids": node_ids})
        node_map = {}
        for record in result:
            node_id = record["node_id"]
            name = record["name"] or f"Node_{node_id}"
            node_map[node_id] = name

        for nid in node_ids:
            if nid not in node_map:
                node_map[nid] = f"Node_{nid}"

        return node_map


def expand_subgraph(anchor_ids: List[int]):
    """
    Returns (nodes, rels) from Neo4j using APOC path expansion.
    """
    if not anchor_ids:
        return [], []

    cypher = """
    MATCH (a:Entity) WHERE a.id IN $ids
    CALL apoc.path.expandConfig(a, {
        relationshipFilter:"TARGETS>|ALLEVIATES>|WORSENED_BY>|TRIGGERED_BY>|HAS_FREQUENCY>|HAS_DURATION>|HAS_SEVERITY>|OCCURRED_AT>|NEGATES>|RELATED_TO>|TARGETS<|ALLEVIATES<|WORSENED_BY<|TRIGGERED_BY<|HAS_FREQUENCY<|HAS_DURATION<|HAS_SEVERITY<|OCCURRED_AT<|NEGATES<|RELATED_TO<",
        maxLevel:1,
        bfs:true,
        limit:5,
        uniqueness:"NODE_GLOBAL"
    }) YIELD path

    WITH collect(DISTINCT a) AS anchors, collect(path) AS paths

    WITH
        apoc.coll.toSet(anchors) +
        apoc.coll.toSet([n IN apoc.coll.flatten([p IN paths | nodes(p)]) | n]) AS nodes,
        apoc.coll.toSet([r IN apoc.coll.flatten([p IN paths | relationships(p)]) | r]) AS rels

    RETURN nodes, rels
    """

    with driver.session() as session:
        rec = session.run(cypher, {"ids": anchor_ids}).single()
        if not rec:
            return [], []
        return rec["nodes"], rec["rels"]
