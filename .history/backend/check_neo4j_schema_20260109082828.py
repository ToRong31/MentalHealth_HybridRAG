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
    
    # Get a sample node
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            RETURN n, labels(n) as labels, keys(n) as properties
            LIMIT 1
            """
        )
        record = result.single()
        
        if record:
            node = record['n']
            print(f"Labels: {record['labels']}")
            print(f"Properties: {record['properties']}")
            print(f"\nNode content:")
            for key in node.keys():
                value = node[key]
                if isinstance(value, str) and len(value) > 200:
                    print(f"  {key}: {value[:200]}...")
                else:
                    print(f"  {key}: {value}")
        else:
            print("Node not found")
    
    driver.close()
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
