"""
Check Milvus collections from inside backend container
"""
from pymilvus import MilvusClient
import os

MILVUS_URI = os.getenv("MILVUS_URI", "http://milvus-standalone:19530")

print("="*80)
print("🔍 CHECKING MILVUS COLLECTIONS")
print("="*80)
print(f"MILVUS_URI: {MILVUS_URI}")
print()

try:
    client = MilvusClient(uri=MILVUS_URI)
    print("✅ Connected to Milvus")
    print()
    
    collections = client.list_collections()
    print(f"📚 Total collections: {len(collections)}")
    print("-"*80)
    
    for collection_name in collections:
        print(f"\n📁 Collection: {collection_name}")
        try:
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get("row_count", 0)
            print(f"   - Documents: {row_count:,}")
            
            if "diagnostic" in collection_name.lower():
                print(f"   ⚠️  THIS IS A DIAGNOSTIC COLLECTION!")
                if row_count == 0:
                    print(f"   ❌ COLLECTION IS EMPTY!")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print()
    print("="*80)
    
    # Check specifically for mental_health_diagnostic_support
    if "mental_health_diagnostic_support" not in collections:
        print()
        print("❌ WARNING: Collection 'mental_health_diagnostic_support' NOT FOUND!")
        print("   Available collections:", collections)
    elif "mental_health_diagnostic_support" in collections:
        stats = client.get_collection_stats("mental_health_diagnostic_support")
        row_count = stats.get("row_count", 0)
        if row_count == 0:
            print()
            print("❌ WARNING: Collection 'mental_health_diagnostic_support' EXISTS but is EMPTY!")
        else:
            print()
            print(f"✅ Collection 'mental_health_diagnostic_support' exists with {row_count:,} documents")
            
except Exception as e:
    print(f"❌ Error: {e}")
