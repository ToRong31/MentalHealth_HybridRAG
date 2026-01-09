"""
COMPREHENSIVE TREATMENT RETRIEVAL DIAGNOSTIC
Tests ALL possible failure points in treatment retrieval flow
Does NOT stop at first error - collects ALL issues
"""
import sys
import os
sys.path.insert(0, "/app")

import json
import asyncio
from pathlib import Path
from pymilvus import MilvusClient, Collection, connections
from sentence_transformers import SentenceTransformer

print("="*80)
print("🔍 COMPREHENSIVE TREATMENT RETRIEVAL DIAGNOSTIC")
print("="*80)
print("This will check ALL possible failure points:")
print("1. Treatment mapping file exists and valid")
print("2. Disease names in mapping")
print("3. Milvus collection exists and has data")
print("4. Field 'disease' exists in schema")
print("5. Actual disease values in collection")
print("6. Fuzzy matching logic")
print("7. Embedding + retrieval")
print("="*80)
print()

# Track all errors
errors = []
warnings = []
successes = []

# Test disease name
test_disease = "Depressive Disorders"
print(f"🎯 Testing with disease: '{test_disease}'")
print()

# ============================================================================
# TEST 1: Treatment mapping file
# ============================================================================
print("TEST 1: Treatment mapping file")
print("-" * 40)
mapping_path = Path("/app/data/raw/treatment_mapping.json")
mapping = {}

try:
    if not mapping_path.exists():
        errors.append(f"❌ TEST 1 FAILED: Mapping file not found at {mapping_path}")
        print(errors[-1])
    else:
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        successes.append(f"✅ TEST 1 PASSED: Mapping file loaded with {len(mapping)} diseases")
        print(successes[-1])
        
        # Check if test disease is in mapping
        if test_disease in mapping:
            titles = mapping[test_disease]
            print(f"   ✓ '{test_disease}' found in mapping → {len(titles)} titles")
            print(f"   Titles: {titles[:3]}..." if len(titles) > 3 else f"   Titles: {titles}")
        else:
            warnings.append(f"⚠️  '{test_disease}' NOT in mapping (fuzzy matching will be tested)")
            print(warnings[-1])
            
            # Show similar keys
            print(f"   Available keys containing 'Depressive':")
            for key in mapping.keys():
                if 'depressive' in key.lower():
                    print(f"     - {key} → {len(mapping[key])} titles")
except Exception as e:
    errors.append(f"❌ TEST 1 FAILED: Error loading mapping: {e}")
    print(errors[-1])

print()

# ============================================================================
# TEST 2: Milvus connection and collection
# ============================================================================
print("TEST 2: Milvus collection")
print("-" * 40)

try:
    connections.connect(host="milvus-standalone", port="19530")
    successes.append("✅ TEST 2.1 PASSED: Connected to Milvus")
    print(successes[-1])
    
    collection_name = "mental_health_treatment_guidance"
    
    # Check collection exists
    from pymilvus import utility
    if not utility.has_collection(collection_name):
        errors.append(f"❌ TEST 2.2 FAILED: Collection '{collection_name}' does not exist")
        print(errors[-1])
    else:
        successes.append(f"✅ TEST 2.2 PASSED: Collection exists")
        print(successes[-1])
        
        col = Collection(collection_name)
        num_entities = col.num_entities
        
        if num_entities == 0:
            errors.append(f"❌ TEST 2.3 FAILED: Collection is empty (0 entities)")
            print(errors[-1])
        else:
            successes.append(f"✅ TEST 2.3 PASSED: Collection has {num_entities} entities")
            print(successes[-1])
        
        # Check schema
        schema = col.schema
        field_names = [field.name for field in schema.fields]
        print(f"   Schema fields: {field_names}")
        
        if 'disease' not in field_names:
            errors.append(f"❌ TEST 2.4 FAILED: Field 'disease' not in schema")
            print(errors[-1])
        else:
            successes.append(f"✅ TEST 2.4 PASSED: Field 'disease' exists in schema")
            print(successes[-1])
        
        if 'title' in field_names:
            warnings.append(f"⚠️  Field 'title' also exists (might cause confusion)")
            print(warnings[-1])
            
except Exception as e:
    errors.append(f"❌ TEST 2 FAILED: Milvus error: {e}")
    print(errors[-1])

print()

# ============================================================================
# TEST 3: Query actual disease values in collection
# ============================================================================
print("TEST 3: Actual disease values in collection")
print("-" * 40)

try:
    col.load()
    
    # Query first 100 records to see disease values
    results = col.query(
        expr="node_id != ''",
        output_fields=["node_id", "disease"],
        limit=100
    )
    
    if not results:
        errors.append(f"❌ TEST 3.1 FAILED: No results from query")
        print(errors[-1])
    else:
        successes.append(f"✅ TEST 3.1 PASSED: Retrieved {len(results)} sample records")
        print(successes[-1])
        
        # Extract unique disease values
        unique_diseases = set()
        for r in results:
            if 'disease' in r:
                unique_diseases.add(r['disease'])
        
        print(f"   Found {len(unique_diseases)} unique disease values in sample:")
        for disease in sorted(unique_diseases)[:10]:
            print(f"     - {disease}")
        
        if len(unique_diseases) > 10:
            print(f"     ... and {len(unique_diseases) - 10} more")
        
        # Check if test disease exists
        matching_diseases = [d for d in unique_diseases if 'depressive' in d.lower()]
        if matching_diseases:
            successes.append(f"✅ TEST 3.2 PASSED: Found {len(matching_diseases)} diseases containing 'depressive'")
            print(successes[-1])
            for d in matching_diseases:
                print(f"     - {d}")
        else:
            errors.append(f"❌ TEST 3.2 FAILED: No diseases containing 'depressive' found in sample")
            print(errors[-1])
            
except Exception as e:
    errors.append(f"❌ TEST 3 FAILED: Query error: {e}")
    print(errors[-1])

print()

# ============================================================================
# TEST 4: Fuzzy matching logic
# ============================================================================
print("TEST 4: Fuzzy matching logic")
print("-" * 40)

def normalize_disease_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = normalized.replace('-related', '').replace(' related', '')
    return normalized

def find_treatment_titles(disease_name: str, mapping: dict) -> list:
    """Test the fuzzy matching logic"""
    ABBREVIATIONS = {
        "ptsd": "Posttraumatic Stress Disorder",
        "ocd": "Obsessive-Compulsive Disorder",
        "adhd": "Attention-Deficit/Hyperactivity Disorder",
        "gad": "Generalized Anxiety Disorder",
        "sad": "Social Anxiety Disorder",
        "mdd": "Major Depressive Disorder",
        "bpd": "Borderline Personality Disorder",
        "aspd": "Antisocial Personality Disorder"
    }
    
    normalized_query = normalize_disease_name(disease_name)
    
    # Tier 1: Abbreviation expansion
    if normalized_query in ABBREVIATIONS:
        expanded = ABBREVIATIONS[normalized_query]
        if expanded in mapping:
            return mapping[expanded]
    
    # Tier 2: Exact match
    for key in mapping.keys():
        if normalize_disease_name(key) == normalized_query:
            return mapping[key]
    
    # Tier 3: Singular/Plural variants
    for key in mapping.keys():
        key_norm = normalize_disease_name(key)
        # Strip trailing 's' for comparison
        if key_norm.rstrip('s') == normalized_query.rstrip('s'):
            return mapping[key]
    
    # Tier 4: Partial match (contains)
    for key in mapping.keys():
        key_norm = normalize_disease_name(key)
        if normalized_query in key_norm or key_norm in normalized_query:
            return mapping[key]
    
    # Tier 5: Keyword matching
    query_words = set(normalized_query.split())
    best_match = None
    best_score = 0
    
    for key in mapping.keys():
        key_words = set(normalize_disease_name(key).split())
        common = query_words & key_words
        if len(common) > best_score:
            best_score = len(common)
            best_match = key
    
    if best_match and best_score > 0:
        return mapping[best_match]
    
    return []

try:
    if mapping:
        titles = find_treatment_titles(test_disease, mapping)
        if titles:
            successes.append(f"✅ TEST 4 PASSED: Fuzzy matching found {len(titles)} titles for '{test_disease}'")
            print(successes[-1])
            print(f"   Matched titles: {titles[:3]}..." if len(titles) > 3 else f"   Matched titles: {titles}")
        else:
            errors.append(f"❌ TEST 4 FAILED: Fuzzy matching returned 0 titles for '{test_disease}'")
            print(errors[-1])
    else:
        warnings.append(f"⚠️  TEST 4 SKIPPED: No mapping loaded")
        print(warnings[-1])
except Exception as e:
    errors.append(f"❌ TEST 4 FAILED: Fuzzy matching error: {e}")
    print(errors[-1])

print()

# ============================================================================
# TEST 5: Filter query with IN operator
# ============================================================================
print("TEST 5: Milvus IN filter query")
print("-" * 40)

try:
    if mapping and titles:
        # Test if titles exist as disease values
        col.load()
        
        # Use proper IN syntax
        titles_str = '", "'.join(titles[:5])  # Test first 5 titles
        expr = f'disease in ["{titles_str}"]'
        
        print(f"   Testing filter expression: {expr[:100]}...")
        
        results = col.query(
            expr=expr,
            output_fields=["node_id", "disease"],
            limit=10
        )
        
        if results:
            successes.append(f"✅ TEST 5 PASSED: IN filter returned {len(results)} results")
            print(successes[-1])
            for r in results[:3]:
                print(f"     - {r.get('node_id')}: {r.get('disease')}")
        else:
            errors.append(f"❌ TEST 5 FAILED: IN filter returned 0 results")
            print(errors[-1])
            
            # Debug: Check if ANY title exists
            print(f"   Debugging: Checking each title individually...")
            for title in titles[:3]:
                try:
                    test_results = col.query(
                        expr=f'disease == "{title}"',
                        output_fields=["node_id", "disease"],
                        limit=1
                    )
                    if test_results:
                        print(f"     ✓ Found: '{title}'")
                    else:
                        print(f"     ✗ Not found: '{title}'")
                except Exception as e:
                    print(f"     ✗ Error testing '{title}': {e}")
    else:
        warnings.append(f"⚠️  TEST 5 SKIPPED: No titles to test")
        print(warnings[-1])
        
except Exception as e:
    errors.append(f"❌ TEST 5 FAILED: IN filter error: {e}")
    print(errors[-1])

print()

# ============================================================================
# TEST 6: Full embedding + retrieval
# ============================================================================
print("TEST 6: Embedding + vector search")
print("-" * 40)

try:
    if titles:
        print("   Loading E5 model...")
        model = SentenceTransformer("intfloat/e5-large-v2")
        
        # Create query embedding
        query_texts = [f"query: {title}" for title in titles[:3]]
        embeddings = model.encode(query_texts)
        
        print(f"   Created {len(embeddings)} embeddings")
        
        # Search with first embedding
        col.load()
        search_results = col.search(
            data=[embeddings[0].tolist()],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=5,
            output_fields=["node_id", "disease"]
        )
        
        if search_results and len(search_results[0]) > 0:
            successes.append(f"✅ TEST 6 PASSED: Vector search returned {len(search_results[0])} results")
            print(successes[-1])
            for hit in search_results[0][:3]:
                print(f"     - Score: {hit.distance:.4f}, Disease: {hit.entity.get('disease')}")
        else:
            errors.append(f"❌ TEST 6 FAILED: Vector search returned 0 results")
            print(errors[-1])
    else:
        warnings.append(f"⚠️  TEST 6 SKIPPED: No titles to test")
        print(warnings[-1])
        
except Exception as e:
    errors.append(f"❌ TEST 6 FAILED: Embedding/search error: {e}")
    print(errors[-1])

print()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("="*80)
print("📊 DIAGNOSTIC SUMMARY")
print("="*80)

print(f"\n✅ SUCCESSES ({len(successes)}):")
for s in successes:
    print(f"  {s}")

print(f"\n⚠️  WARNINGS ({len(warnings)}):")
if warnings:
    for w in warnings:
        print(f"  {w}")
else:
    print("  None")

print(f"\n❌ ERRORS ({len(errors)}):")
if errors:
    for e in errors:
        print(f"  {e}")
else:
    print("  None - All tests passed!")

print("\n" + "="*80)

# Exit code based on errors
if errors:
    print(f"❌ DIAGNOSTIC FAILED: {len(errors)} error(s) found")
    sys.exit(1)
else:
    print(f"✅ DIAGNOSTIC PASSED: All tests successful")
    sys.exit(0)
