"""
Check Treatment Collection in Milvus
"""
import sys
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from rag.config import rag_settings

print("="*80)
print("🔍 CHECKING TREATMENT COLLECTION")
print("="*80)

try:
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus")
    print()
    
    # Check treatment collection
    collection_name = "mental_health_treatment_guidance"
    
    # Check if exists
    collections = client.list_collections()
    print(f"Available collections: {collections}")
    print()
    
    if collection_name in collections:
        print(f"✅ Collection '{collection_name}' exists")
        
        # Get stats
        stats = client.get_collection_stats(collection_name)
        print(f"Collection stats: {stats}")
        
        # Count documents
        count = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["count(*)"]
        )
        print(f"Total documents: {count}")
        print()
        
        # Sample search
        print("Testing sample search...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(rag_settings.E5_MODEL_NAME)
        
        test_query = "treatment for depression"
        embedding = model.encode([f"query: {test_query}"])[0].tolist()
        
        results = client.search(
            collection_name=collection_name,
            data=[embedding],
            limit=5,
            output_fields=["node_id", "disease"],
            search_params={"metric_type": "COSINE", "params": {}}
        )
        
        if results and results[0]:
            print(f"✅ Found {len(results[0])} results for '{test_query}':")
            for i, hit in enumerate(results[0], 1):
                disease = hit['entity'].get('disease', 'Unknown')
                score = hit['distance']
                node_id = hit['entity'].get('node_id', 'Unknown')
                print(f"  {i}. Disease: {disease:40s} | Score: {score:.4f} | Node: {node_id}")
        else:
            print("❌ No results found")
            
    else:
        print(f"❌ Collection '{collection_name}' NOT FOUND")
        print()
        print("Available collections:")
        for col in collections:
            stats = client.get_collection_stats(col)
            print(f"  - {col}: {stats}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("="*80)
