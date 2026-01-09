"""
Test Treatment Retrieval - Full Integration Test
Tests: async file loading, field names, fuzzy matching, Milvus query
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from pymilvus import connections, Collection
from src.rag.config import rag_settings
from src.rag.vectors.embeddings import encode_e5
from src.rag.workflow.graph_nodes.treatment_retrieval import (
    load_treatment_mapping,
    find_treatment_titles,
    normalize_disease_name
)


async def test_async_mapping_load():
    """Test 1: Async file loading"""
    print("=" * 80)
    print("TEST 1: ASYNC MAPPING LOAD")
    print("=" * 80)
    
    mapping = await load_treatment_mapping()
    print(f"✅ Loaded {len(mapping)} diseases")
    print(f"   Sample keys: {list(mapping.keys())[:3]}")
    return mapping


def test_field_names():
    """Test 2: Milvus field names"""
    print("\n" + "=" * 80)
    print("TEST 2: MILVUS FIELD NAMES")
    print("=" * 80)
    
    # Connect to Milvus
    connections.connect(
        alias="default",
        uri=rag_settings.MILVUS_URI,
        db_name=rag_settings.MILVUS_DB
    )
    
    col = Collection("mental_health_treatment_guidance")
    col.load()
    
    # Check schema
    print(f"📊 Collection: {col.name}")
    print(f"   Fields: {[field.name for field in col.schema.fields]}")
    
    # Sample query
    results = col.query(
        expr="",
        limit=2,
        output_fields=["chunk_id", "title"]
    )
    
    print(f"\n✅ Sample records:")
    for i, record in enumerate(results, 1):
        print(f"   {i}. chunk_id={record.get('chunk_id')}, title='{record.get('title')[:50]}...'")
    
    connections.disconnect("default")


def test_fuzzy_matching(mapping):
    """Test 3: Fuzzy matching logic"""
    print("\n" + "=" * 80)
    print("TEST 3: FUZZY MATCHING")
    print("=" * 80)
    
    test_cases = [
        ("Depressive Disorders", "Depressive Disorders"),  # Exact
        ("Depressive Disorder", "Depressive Disorders"),   # Singular
        ("PTSD", "Posttraumatic Stress Disorder"),         # Abbreviation
        ("OCD", "Obsessive-Compulsive Disorder"),          # Abbreviation
    ]
    
    for input_name, expected_key in test_cases:
        titles = find_treatment_titles(input_name, mapping)
        matched = len(titles) > 0
        
        if matched:
            # Find which key matched
            matched_key = None
            for key, vals in mapping.items():
                if set(vals) == set(titles):
                    matched_key = key
                    break
            
            status = "✅ PASS" if matched_key == expected_key else "⚠️ PARTIAL"
            print(f"{status}: '{input_name}' → '{matched_key}' ({len(titles)} titles)")
        else:
            print(f"❌ FAIL: '{input_name}' → No match (expected '{expected_key}')")


async def test_milvus_query(mapping):
    """Test 4: Full Milvus query with IN filter"""
    print("\n" + "=" * 80)
    print("TEST 4: MILVUS QUERY WITH IN FILTER")
    print("=" * 80)
    
    # Connect to Milvus
    connections.connect(
        alias="default",
        uri=rag_settings.MILVUS_URI,
        db_name=rag_settings.MILVUS_DB
    )
    
    col = Collection("mental_health_treatment_guidance")
    col.load()
    
    # Test disease
    test_disease = "Depressive Disorders"
    titles = find_treatment_titles(test_disease, mapping)
    print(f"🔍 Disease: {test_disease}")
    print(f"   Treatment titles: {titles}")
    
    if not titles:
        print("❌ No titles found, cannot test Milvus query")
        return
    
    # Build filter expression
    escaped_titles = [title.replace('"', '\\"').replace("'", "\\'") for title in titles]
    title_list_str = ", ".join([f'"{title}"' for title in escaped_titles])
    expr = f'title in [{title_list_str}]'
    
    print(f"\n📝 Milvus filter expression:")
    print(f"   {expr}")
    
    # Encode query
    query = "Cách điều trị trầm cảm"
    encoded = encode_e5([f"query: {query}"])
    query_vector = encoded[0].tolist()
    
    # Search
    results = col.search(
        data=[query_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 64}},
        limit=5,
        expr=expr,
        output_fields=["node_id", "title"]
    )
    
    hits = results[0] if results else []
    print(f"\n✅ Found {len(hits)} results:")
    for i, hit in enumerate(hits, 1):
        print(f"   {i}. node_id={hit.entity.get('node_id')}, score={hit.distance:.4f}")
        print(f"      title='{hit.entity.get('title')}'")
    
    connections.disconnect("default")


async def main():
    print("🧪 TREATMENT RETRIEVAL - FULL INTEGRATION TEST")
    print("=" * 80)
    
    # Test 1: Async mapping load
    mapping = await test_async_mapping_load()
    
    # Test 2: Field names
    test_field_names()
    
    # Test 3: Fuzzy matching
    test_fuzzy_matching(mapping)
    
    # Test 4: Full Milvus query
    await test_milvus_query(mapping)
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
