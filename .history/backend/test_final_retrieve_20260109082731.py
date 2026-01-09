"""
Final script to retrieve the specific diagnostic text from Milvus + Neo4j
"""
import sys
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
from rag.config import rag_settings
from neo4j import GraphDatabase

print("="*80)
print("🔍 RETRIEVING DIAGNOSTIC TEXT")
print("="*80)
print(f"MILVUS_URI: {rag_settings.MILVUS_URI}")
print(f"NEO4J_URI: {rag_settings.NEO4J_URI}")
print()

# Query text
query_text = "There is often a localized uncomfortable sensation (premonitory sensation) prior to a tic, and most individuals report an \"urge\" to tic."

print(f"Query text: {query_text}")
print()

try:
    # Initialize embedding model
    print("📦 Loading E5 model...")
    model = SentenceTransformer(rag_settings.E5_MODEL_NAME)
    print("✅ E5 model loaded\n")
    
    # Create embedding for query
    print("🔄 Creating query embedding...")
    query_embedding = model.encode([f"query: {query_text}"])[0].tolist()
    print(f"✅ Embedding created (dim: {len(query_embedding)})\n")
    
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus\n")
    
    # Search in diagnostic support collection
    collection_name = "mental_health_diagnostic_support"
    print(f"🔍 Searching in: {collection_name}")
    print("-"*80)
    
    # Search
    results = client.search(
        collection_name=collection_name,
        data=[query_embedding],
        limit=5,
        output_fields=["node_id", "disease"],
        search_params={"metric_type": "COSINE", "params": {}}
    )
    
    print(f"Found {len(results[0])} results\n")
    
    # Connect to Neo4j
    print("📊 Connecting to Neo4j...")
    neo4j_driver = GraphDatabase.driver(
        rag_settings.NEO4J_URI,
        auth=(rag_settings.NEO4J_USER, rag_settings.NEO4J_PASSWORD)
    )
    print("✅ Connected to Neo4j\n")
    
    # Get text content from Neo4j for each result
    for i, hit in enumerate(results[0], 1):
        node_id = hit['entity'].get('node_id')
        disease = hit['entity'].get('disease')
        score = hit['distance']
        
        print(f"Result #{i}")
        print(f"  Score: {score:.4f}")
        print(f"  Disease: {disease}")
        print(f"  Node ID: {node_id}")
        
        # Query Neo4j to get the text content
        with neo4j_driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                WHERE n.id = $node_id
                RETURN n.name as name, n.text as text, labels(n) as labels
                """,
                node_id=node_id
            )
            record = result.single()
            
            if record:
                print(f"  Labels: {record['labels']}")
                print(f"  Name: {record['name']}")
                print(f"  Text: {record['text']}")
            else:
                print(f"  ⚠️  Node not found in Neo4j")
        
        print()
    
    neo4j_driver.close()
    print("="*80)
    print("✅ RETRIEVAL COMPLETED")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
