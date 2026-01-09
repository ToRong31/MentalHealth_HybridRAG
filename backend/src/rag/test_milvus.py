"""
Test script to check normal_responses collection schema and sample data in Milvus
"""

from pymilvus import Collection, connections, utility
from src.rag.config import rag_settings
import sys


def test_normal_responses_collection():
    """Check schema and sample data from normal_responses collection"""
    
    print("=" * 80)
    print("TESTING NORMAL_RESPONSES COLLECTION IN MILVUS")
    print("=" * 80)
    
    # Step 1: Connect to Milvus
    print("\n[STEP 1] Connecting to Milvus...")
    try:
        if not connections.has_connection("default"):
            connection_params = {
                "alias": "default",
                "uri": rag_settings.MILVUS_URI,
                "db_name": rag_settings.MILVUS_DB,
            }
            if rag_settings.MILVUS_TOKEN and rag_settings.MILVUS_TOKEN.strip():
                connection_params["token"] = rag_settings.MILVUS_TOKEN
                connection_params["secure"] = True
            else:
                connection_params["secure"] = False
            connections.connect(**connection_params)
        print(f"✅ Connected to Milvus: {rag_settings.MILVUS_URI}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    # Step 2: Check if collection exists
    print("\n[STEP 2] Checking collection existence...")
    collection_name = "normal_responses"
    
    if collection_name not in utility.list_collections():
        print(f"❌ Collection '{collection_name}' does not exist!")
        print(f"Available collections: {utility.list_collections()}")
        return
    
    print(f"✅ Collection '{collection_name}' exists")
    
    # Step 3: Load collection and show schema
    print("\n[STEP 3] Loading collection and checking schema...")
    try:
        col = Collection(collection_name)
        col.load()
        
        print(f"\n📋 Collection Schema:")
        print(f"  Collection Name: {col.name}")
        print(f"  Description: {col.description}")
        
        schema = col.schema
        print(f"\n  Fields:")
        for field in schema.fields:
            field_info = f"    - {field.name} ({field.dtype})"
            if field.is_primary:
                field_info += " [PRIMARY KEY]"
            if hasattr(field, 'max_length') and field.max_length:
                field_info += f" [max_length={field.max_length}]"
            if hasattr(field, 'dim') and field.dim:
                field_info += f" [dim={field.dim}]"
            print(field_info)
        
        # Get collection stats
        print(f"\n  Statistics:")
        print(f"    Total entities: {col.num_entities}")
        
    except Exception as e:
        print(f"❌ Error loading collection: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Retrieve sample data
    print("\n[STEP 4] Retrieving sample data...")
    try:
        # Query for first 5 records
        results = col.query(
            expr="",  # Empty expr to get all
            output_fields=["node_id", "title", "type", "severity_score"],
            limit=5
        )
        
        print(f"\n📊 Sample Data (first 5 records):")
        print("-" * 80)
        
        for i, record in enumerate(results, 1):
            print(f"\nRecord {i}:")
            print(f"  node_id: {record.get('node_id')}")
            print(f"  title: {record.get('title')}")
            print(f"  type: {record.get('type')}")
            print(f"  severity_score: {record.get('severity_score')}")
        
    except Exception as e:
        print(f"❌ Error querying data: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Test search functionality
    print("\n[STEP 5] Testing search functionality...")
    try:
        from src.rag.vectors.embeddings import encode_e5
        
        # Create a test query embedding
        test_query = "Tôi đang stress vì công việc"
        query_embedding = encode_e5([f"query: {test_query}"])[0].tolist()
        
        print(f"  Test query: '{test_query}'")
        
        # Search in Milvus
        search_results = col.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=5,
            output_fields=["node_id", "title", "type", "severity_score"],
        )
        
        print(f"\n  Top 5 search results:")
        print("-" * 80)
        
        for i, hit in enumerate(search_results[0], 1):
            similarity_score = float(hit.distance)  # This is cosine similarity (0-1)
            entity = hit.entity
            
            # Access the severity_score field (renamed to avoid pymilvus conflict)
            db_severity_score = entity.severity_score if hasattr(entity, 'severity_score') else None
            
            print(f"\n  Result {i}:")
            print(f"    Milvus Similarity: {similarity_score:.4f} (cosine distance)")
            print(f"    node_id: {hit.id}")
            print(f"    title: {entity.title if hasattr(entity, 'title') else 'N/A'}")
            print(f"    type: {entity.type if hasattr(entity, 'type') else 'N/A'}")
            print(f"    Severity Score: {db_severity_score} (from database: -1=common, 1-5=severity, 99=emergency)")
            print(f"    Note: Renamed field from 'score' to 'severity_score' to avoid pymilvus conflict")
        
    except Exception as e:
        print(f"❌ Error testing search: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 6: Check score distribution
    print("\n[STEP 6] Analyzing score distribution...")
    try:
        # Get all records with severity scores
        all_results = col.query(
            expr="",
            output_fields=["node_id", "type", "severity_score"],
            limit=300  # Get more records for analysis
        )
        
        normal_stress_scores = []
        adjustment_reaction_scores = []
        
        for record in all_results:
            score = record.get('severity_score', 0)
            record_type = record.get('type', '').lower()
            
            if 'normal' in record_type or 'stress' in record_type:
                normal_stress_scores.append(score)
            elif 'adjustment' in record_type:
                adjustment_reaction_scores.append(score)
        
        print(f"\n  Score Analysis:")
        print(f"    Normal Stress items: {len(normal_stress_scores)}")
        if normal_stress_scores:
            print(f"      Min: {min(normal_stress_scores)}")
            print(f"      Max: {max(normal_stress_scores)}")
            print(f"      Avg: {sum(normal_stress_scores) / len(normal_stress_scores):.2f}")
        
        print(f"\n    Adjustment Reaction items: {len(adjustment_reaction_scores)}")
        if adjustment_reaction_scores:
            print(f"      Min: {min(adjustment_reaction_scores)}")
            print(f"      Max: {max(adjustment_reaction_scores)}")
            print(f"      Avg: {sum(adjustment_reaction_scores) / len(adjustment_reaction_scores):.2f}")
        
        # Show score distribution buckets
        print(f"\n  Score Distribution:")
        score_buckets = {'-1': 0, '1-5': 0, '6-60': 0, '>60': 0}
        
        all_scores = normal_stress_scores + adjustment_reaction_scores
        for score in all_scores:
            if score == -1:
                score_buckets['-1'] += 1
            elif 1 <= score <= 5:
                score_buckets['1-5'] += 1
            elif 6 <= score <= 60:
                score_buckets['6-60'] += 1
            else:
                score_buckets['>60'] += 1
        
        for bucket, count in score_buckets.items():
            percentage = (count / len(all_scores) * 100) if all_scores else 0
            print(f"    {bucket}: {count} items ({percentage:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error analyzing scores: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    test_normal_responses_collection()
