"""
Script to test retrieval of diagnostic documents from Milvus
Running inside backend container
"""
import sys
import os
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
from rag.config import rag_settings

print("="*80)
print("🔍 TESTING RETRIEVAL FROM MILVUS")
print("="*80)
print(f"MILVUS_URI: {rag_settings.MILVUS_URI}")
print(f"E5_MODEL: {rag_settings.E5_MODEL_NAME}")
print()

# Query text
query_text = "There is often a localized uncomfortable sensation (premonitory sensation) prior to a tic, and most individuals report an \"urge\" to tic."

print(f"Query text: {query_text}")
print()

try:
    # Initialize embedding model
    print("📦 Loading E5 model...")
    model = SentenceTransformer(rag_settings.E5_MODEL_NAME)
    print("✅ E5 model loaded")
    print()
    
    # Create embedding for query
    print("🔄 Creating query embedding...")
    query_embedding = model.encode([f"query: {query_text}"])[0].tolist()
    print(f"✅ Embedding created (dim: {len(query_embedding)})")
    print()
    
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus")
    print()
    
    # List all collections
    collections = client.list_collections()
    print(f"📚 Available collections ({len(collections)}):")
    for col in collections:
        print(f"  - {col}")
    print()
    
    # Search in each collection
    for collection_name in collections:
        print("-"*80)
        print(f"🔍 Searching in collection: {collection_name}")
        print("-"*80)
        
        try:
            # Get collection stats
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get("row_count", 0)
            print(f"📊 Total documents: {row_count}")
            
            if row_count == 0:
                print("⚠️  Collection is empty")
                continue
            
            # Search
            results = client.search(
                collection_name=collection_name,
                data=[query_embedding],
                limit=3,
                output_fields=["text", "chunk_id"],
                search_params={"metric_type": "COSINE", "params": {}}
            )
            
            print(f"\n✅ Found {len(results[0])} results:")
            print()
            
            for i, hit in enumerate(results[0], 1):
                print(f"Result #{i}")
                print(f"  Score: {hit['distance']:.4f}")
                print(f"  Chunk ID: {hit['entity'].get('chunk_id', 'N/A')}")
                text = hit['entity'].get('text', 'N/A')
                if len(text) > 300:
                    print(f"  Text: {text[:300]}...")
                else:
                    print(f"  Text: {text}")
                print()
                
        except Exception as e:
            print(f"❌ Error searching collection {collection_name}: {str(e)}")
            print()
    
    print("="*80)
    print("✅ SEARCH COMPLETED")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
