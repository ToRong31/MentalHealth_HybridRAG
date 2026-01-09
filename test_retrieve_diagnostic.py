"""
Script to test retrieval of diagnostic documents from Milvus
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from pymilvus import MilvusClient
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Load environment variables
env_path = Path(__file__).parent / "backend" / "src" / ".env"
load_dotenv(dotenv_path=env_path)

MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
E5_MODEL_NAME = os.getenv("E5_MODEL_NAME", "intfloat/e5-large-v2")

print("="*80)
print("🔍 TESTING RETRIEVAL FROM MILVUS")
print("="*80)
print(f"MILVUS_URI: {MILVUS_URI}")
print(f"E5_MODEL: {E5_MODEL_NAME}")
print()

# Query text
query_text = "There is often a localized uncomfortable sensation (premonitory sensation) prior to a tic, and most individuals report an \"urge\" to tic."

print(f"Query text: {query_text}")
print()

try:
    # Initialize embedding model
    print("📦 Loading E5 model...")
    model = SentenceTransformer(E5_MODEL_NAME)
    print("✅ E5 model loaded")
    print()
    
    # Create embedding for query
    print("🔄 Creating query embedding...")
    query_embedding = model.encode([f"query: {query_text}"])[0].tolist()
    print(f"✅ Embedding created (dim: {len(query_embedding)})")
    print()
    
    # Connect to Milvus
    client = MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN
    )
    print("✅ Connected to Milvus")
    print()
    
    # List all collections
    collections = client.list_collections()
    print(f"📚 Available collections: {collections}")
    print()
    
    # Search in each collection
    for collection_name in collections:
        if "diagnostic" in collection_name.lower() or "mental" in collection_name.lower():
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
                    limit=5,
                    output_fields=["text", "chunk_id"],
                    search_params={"metric_type": "COSINE", "params": {}}
                )
                
                print(f"\n✅ Found {len(results[0])} results:")
                print()
                
                for i, hit in enumerate(results[0], 1):
                    print(f"Result #{i}")
                    print(f"  Score: {hit['distance']:.4f}")
                    print(f"  Chunk ID: {hit['entity'].get('chunk_id', 'N/A')}")
                    print(f"  Text: {hit['entity'].get('text', 'N/A')[:200]}...")
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
