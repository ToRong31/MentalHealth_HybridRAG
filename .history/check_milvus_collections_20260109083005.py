"""
Script to check Milvus collections and their data
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from pymilvus import MilvusClient, connections
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")

print("="*80)
print("🔍 CHECKING MILVUS COLLECTIONS")
print("="*80)
print(f"MILVUS_URI: {MILVUS_URI}")
print()

try:
    # Create client
    client = MilvusClient(
        uri=MILVUS_URI,
        token=MILVUS_TOKEN
    )
    
    print("✅ Connected to Milvus")
    print()
    
    # List all collections
    collections = client.list_collections()
    print(f"📚 Total collections: {len(collections)}")
    print("-"*80)
    
    for collection_name in collections:
        print(f"\n📁 Collection: {collection_name}")
        
        try:
            # Get collection stats
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get("row_count", 0)
            
            print(f"   - Documents: {row_count:,}")
            
            # Check if this is the diagnostic support collection
            if "diagnostic" in collection_name.lower():
                print(f"   ⚠️  THIS IS A DIAGNOSTIC COLLECTION!")
                
                # Try to query a few documents
                if row_count > 0:
                    print(f"   - Fetching sample documents...")
                    results = client.query(
                        collection_name=collection_name,
                        filter="",
                        output_fields=["text", "title"],
                        limit=3
                    )
                    if results:
                        print(f"   - Sample documents:")
                        for i, doc in enumerate(results[:3], 1):
                            text = doc.get("text", "")[:100]
                            title = doc.get("title", "N/A")
                            print(f"      {i}. Title: {title}")
                            print(f"         Text: {text}...")
                else:
                    print(f"   ❌ COLLECTION IS EMPTY!")
                    
        except Exception as e:
            print(f"   ❌ Error getting stats: {e}")
    
    print()
    print("="*80)
    print("✅ CHECK COMPLETE")
    print("="*80)
    
    # Check specifically for mental_health_diagnostic_support
    if "mental_health_diagnostic_support" not in collections:
        print()
        print("❌ WARNING: Collection 'mental_health_diagnostic_support' NOT FOUND!")
        print("   This explains why diagnostic retrieval is not working.")
        print()
        print("💡 Solution: Run the ingestion script to create and populate this collection:")
        print("   python backend/src/rag/ingestion/ingest_diagnostic.py")
    elif "mental_health_diagnostic_support" in collections:
        stats = client.get_collection_stats("mental_health_diagnostic_support")
        row_count = stats.get("row_count", 0)
        if row_count == 0:
            print()
            print("❌ WARNING: Collection 'mental_health_diagnostic_support' EXISTS but is EMPTY!")
            print("   This explains why diagnostic retrieval returns no results.")
            print()
            print("💡 Solution: Run the ingestion script to populate this collection:")
            print("   python backend/src/rag/ingestion/ingest_diagnostic.py")
        else:
            print()
            print(f"✅ Collection 'mental_health_diagnostic_support' exists with {row_count:,} documents")
    
except Exception as e:
    print(f"❌ Error connecting to Milvus: {e}")
    print()
    print("Make sure:")
    print("  1. Milvus is running (check docker compose)")
    print("  2. MILVUS_URI and MILVUS_TOKEN are set correctly in .env")
