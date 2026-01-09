"""
Check schema of Milvus collections
"""
import sys
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from rag.config import rag_settings

print("="*80)
print("🔍 CHECKING COLLECTION SCHEMAS")
print("="*80)

try:
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus")
    print()
    
    # List all collections
    collections = client.list_collections()
    
    for collection_name in collections:
        print("-"*80)
        print(f"📁 Collection: {collection_name}")
        print("-"*80)
        
        # Describe collection
        desc = client.describe_collection(collection_name)
        
        print(f"Schema:")
        for field in desc['fields']:
            print(f"  - {field['name']} ({field['type']})")
        print()
        
        # Get a sample document
        results = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["*"],
            limit=1
        )
        
        if results:
            print("Sample document fields:")
            for key in results[0].keys():
                value = results[0][key]
                if isinstance(value, str) and len(value) > 100:
                    print(f"  - {key}: {value[:100]}...")
                else:
                    print(f"  - {key}: {value}")
        print()
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
