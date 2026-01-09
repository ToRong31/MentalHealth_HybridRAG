"""
Check Neo4j node schema
"""
import sys
sys.path.insert(0, "/app/src")

from neo4j import GraphDatabase
from rag.config import rag_settings

print("="*80)
print("🔍 CHECKING NEO4J NODE SCHEMA")
print("="*80)

try:
    # Connect to Neo4j
    driver = GraphDatabase.driver(
        rag_settings.NEO4J_URI,
        auth=(rag_settings.NEO4J_USER, rag_settings.NEO4J_PASSWORD)
    )
    print("✅ Connected to Neo4j\n")
    
    # Get total node count
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()['count']
        print(f"Total nodes: {count}\n")
    
    # Get sample nodes with different labels
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            RETURN DISTINCT labels(n) as labels, count(*) as count
            ORDER BY count DESC
            LIMIT 10
            """
        )
        print("Node labels:")
        for record in result:
            print(f"  {record['labels']}: {record['count']}")
        print()
    
    # Search for nodes containing "tic" or "premonitory"
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS 'tic' OR toLower(n.name) CONTAINS 'premonitory'
            RETURN n, labels(n) as labels
            LIMIT 5
            """
        )
        print("Nodes containing 'tic' or 'premonitory':")
        for record in result:
            node = record['n']
            print(f"  Labels: {record['labels']}")
            print(f"  ID: {node.get('id')}")
            print(f"  Name: {node.get('name')}")
            print()
    
    driver.close()
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
