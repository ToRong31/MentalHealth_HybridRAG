from neo4j import GraphDatabase
import csv
from pathlib import Path
import sys
import os

# ========= CONFIG =========
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "torong31102005"
NODES_PATH = Path("../Output/nodes.csv")
EDGES_PATH = Path("../Output/edges.csv")
BATCH = 10_000
USE_APOC = True
# =========================

print(f"[DEBUG] Connecting to {NEO4J_URI}...")
print(f"[DEBUG] User: {NEO4J_USER}")
print(f"[DEBUG] Nodes path: {NODES_PATH.absolute()}")
print(f"[DEBUG] Edges path: {EDGES_PATH.absolute()}")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    print("[DEBUG] ✅ Connected to Neo4j")
except Exception as e:
    print(f"[ERROR] Cannot connect to Neo4j: {e}")
    exit(1)

def run(q, params=None):
    try:
        with driver.session() as s:
            result = list(s.run(q, params or {}))
            return result
    except Exception as e:
        print(f"[ERROR] Query failed: {e}")
        print(f"[ERROR] Query: {q[:200]}...")
        raise

def ensure_constraints():
    print("[INFO] Creating constraints...")
    try:
        run("""CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
               FOR (e:Entity) REQUIRE e.id IS UNIQUE;""")
        print("[INFO] ✅ Constraints created")
    except Exception as e:
        print(f"[WARN] Constraint error: {e}")

def chunker(iterable, size):
    batch = []
    for row in iterable:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch

def apoc_available():
    try:
        v = run("RETURN apoc.version() AS v")[0]["v"]
        print(f"[INFO] APOC: {v}")
        return True
    except Exception:
        print("[WARN] APOC not available; falling back.")
        return False

def load_nodes_apoc(rows):
    q = """
    UNWIND $rows AS row
    WITH row,
         toInteger(row.id) AS id,
         row.name          AS name,
         row.label         AS label
    MERGE (e:Entity {id:id})
      ON CREATE SET e.name = name, e.label = label
      ON MATCH  SET e.name = name, e.label = label
    WITH e, label
    CALL apoc.create.addLabels(e, [label]) YIELD node
    RETURN count(*) AS c
    """
    run(q, {"rows": rows})

def load_nodes_noapoc(rows):
    q = """
    UNWIND $rows AS row
    WITH row,
         toInteger(row.id) AS id,
         row.name          AS name,
         row.label         AS label
    MERGE (e:Entity {id:id})
      ON CREATE SET e.name = name, e.label = label
      ON MATCH  SET e.name = name, e.label = label
    FOREACH (_ IN CASE WHEN label='SYMPTOM'         THEN [1] ELSE [] END | SET e:SYMPTOM)
    FOREACH (_ IN CASE WHEN label='CONDITION'       THEN [1] ELSE [] END | SET e:CONDITION)
    FOREACH (_ IN CASE WHEN label='COPING_STRATEGY' THEN [1] ELSE [] END | SET e:COPING_STRATEGY)
    FOREACH (_ IN CASE WHEN label='INTERVENTION'    THEN [1] ELSE [] END | SET e:INTERVENTION)
    FOREACH (_ IN CASE WHEN label='MEDICATION'      THEN [1] ELSE [] END | SET e:MEDICATION)
    RETURN count(*) AS c
    """
    run(q, {"rows": rows})

def load_edges_apoc(rows):
    q = """
    UNWIND $rows AS row
    WITH toInteger(row.start_id) AS sid,
         toInteger(row.end_id)   AS tid,
         row.type                AS rtype,
         row.source_indices      AS src
    MATCH (s:Entity {id:sid})
    MATCH (t:Entity {id:tid})
    WITH s,t,rtype,
         CASE WHEN src IS NULL OR trim(src)='' THEN []
              ELSE [x IN split(src, ',') | toInteger(trim(x))]
         END AS src_list
    CALL apoc.create.relationship(s, rtype, {source_indices: src_list}, t) YIELD rel
    RETURN count(*) AS c
    """
    run(q, {"rows": rows})

def load_edges_noapoc(rows):
    q = """
    UNWIND $rows AS row
    WITH toInteger(row.start_id) AS sid,
         toInteger(row.end_id)   AS tid,
         row.type                AS rtype,
         row.source_indices      AS src
    MATCH (s:Entity {id:sid})
    MATCH (t:Entity {id:tid})
    WITH s,t,rtype,
         CASE WHEN src IS NULL OR trim(src)='' THEN []
              ELSE [x IN split(src, ',') | toInteger(trim(x))]
         END AS src_list
    FOREACH (_ IN CASE WHEN rtype='TARGETS'      THEN [1] ELSE [] END | MERGE (s)-[r:TARGETS]->(t)      SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='ALLEVIATES'   THEN [1] ELSE [] END | MERGE (s)-[r:ALLEVIATES]->(t)   SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='RELATED_TO'   THEN [1] ELSE [] END | MERGE (s)-[r:RELATED_TO]->(t)   SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='WORSENED_BY'  THEN [1] ELSE [] END | MERGE (s)-[r:WORSENED_BY]->(t)  SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='TRIGGERED_BY' THEN [1] ELSE [] END | MERGE (s)-[r:TRIGGERED_BY]->(t) SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='HAS_FREQUENCY' THEN [1] ELSE [] END | MERGE (s)-[r:HAS_FREQUENCY]->(t) SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='HAS_DURATION'  THEN [1] ELSE [] END | MERGE (s)-[r:HAS_DURATION]->(t)  SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='HAS_SEVERITY'  THEN [1] ELSE [] END | MERGE (s)-[r:HAS_SEVERITY]->(t)  SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='OCCURRED_AT'   THEN [1] ELSE [] END | MERGE (s)-[r:OCCURRED_AT]->(t)   SET r.source_indices=src_list)
    FOREACH (_ IN CASE WHEN rtype='NEGATES'       THEN [1] ELSE [] END | MERGE (s)-[r:NEGATES]->(t)       SET r.source_indices=src_list)
    RETURN 0 AS _
    """
    run(q, {"rows": rows})

def stream_nodes():
    print(f"[INFO] Loading nodes from {NODES_PATH}...")
    if not NODES_PATH.exists():
        print(f"[ERROR] Not found: {NODES_PATH}")
        return 0
    
    try:
        with NODES_PATH.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total = 0
            use_apoc = USE_APOC and apoc_available()
            print(f"[INFO] Using {'APOC' if use_apoc else 'Cypher'} for nodes")
            
            for batch in chunker(reader, BATCH):
                (load_nodes_apoc if use_apoc else load_nodes_noapoc)(batch)
                total += len(batch)
                print(f"[NODES] imported {total}")
            return total
    except Exception as e:
        print(f"[ERROR] Failed to load nodes: {e}")
        raise

def stream_edges():
    print(f"[INFO] Loading edges from {EDGES_PATH}...")
    if not EDGES_PATH.exists():
        print(f"[ERROR] Not found: {EDGES_PATH}")
        return 0
    
    try:
        with EDGES_PATH.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            total = 0
            use_apoc = USE_APOC and apoc_available()
            print(f"[INFO] Using {'APOC' if use_apoc else 'Cypher'} for edges")
            
            for batch in chunker(reader, BATCH):
                (load_edges_apoc if use_apoc else load_edges_noapoc)(batch)
                total += len(batch)
                print(f"[EDGES] imported {total}")
            return total
    except Exception as e:
        print(f"[ERROR] Failed to load edges: {e}")
        raise

def main():
    print("\n=== STARTING IMPORT ===\n")
    try:
        ensure_constraints()
        n = stream_nodes()
        e = stream_edges()
        print(f"\n✅ DONE. nodes={n}, edges={e}")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
    finally:
        driver.close()
        print("[DEBUG] Connection closed")

if __name__ == "__main__":
    main()