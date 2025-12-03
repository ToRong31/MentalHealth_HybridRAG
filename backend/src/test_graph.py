"""
Simple Graph Retrieval Testing Script
Run: python3 -m src.test_graph
"""
from src.rag.retrieval.graph_retrieval import graph_retrieval


def print_separator(title=""):
    """Print a nice separator"""
    print("\n" + "="*70)
    if title:
        print(f"{title}")
        print("="*70)
    print()


def test_query(query: str, **kwargs):
    """Test a single query and print results"""
    print(f"Query: {query}")
    if kwargs:
        print(f"Params: {kwargs}")
    print("-" * 70)
    
    try:
        result = graph_retrieval.retrieve(query, **kwargs)
        
        # Print metadata
        print(f"\n[Metadata]")
        print(f"  Retriever: {result.metadata.get('retriever')}")
        print(f"  Milvus candidates: {result.metadata.get('milvus_candidates', 0)}")
        print(f"  Anchors found: {len(result.metadata.get('anchors', []))}")
        print(f"  Nodes count: {result.metadata.get('nodes_count', 0)}")
        print(f"  Relationships count: {result.metadata.get('rels_count', 0)}")
        
        # Print Milvus scores (before reranking)
        milvus_scores = result.metadata.get('milvus_scores', [])
        if milvus_scores:
            print(f"\n[Milvus Candidates] (Top {min(10, len(milvus_scores))} of {len(milvus_scores)})")
            for i, item in enumerate(milvus_scores[:10], 1):
                print(f"  {i}. {item.get('name')} (ID: {item.get('node_id')}) - Score: {item.get('milvus_score', 0):.4f}")
        
        # Print rerank scores (after reranking)
        rerank_scores = result.metadata.get('rerank_scores', [])
        if rerank_scores:
            print(f"\n[After Reranking] (Top {len(rerank_scores)})")
            for i, item in enumerate(rerank_scores, 1):
                print(f"  {i}. {item.get('name')} (ID: {item.get('node_id')})")
                print(f"     Milvus: {item.get('milvus_score', 0):.4f} → Rerank: {item.get('rerank_score', 0):.4f}")
        
        # Print anchor details (legacy, can be removed if redundant)
        if result.metadata.get('anchors'):
            print(f"\n[Final Anchor Nodes]")
            for i, anchor in enumerate(result.metadata['anchors'], 1):
                print(f"  {i}. {anchor.get('name')} (ID: {anchor.get('node_id')})")
        
        # Print context
        print(f"\n[Context] ({len(result.context)} chars)")
        if result.context:
            print(result.context)
        else:
            print("  (empty)")
        
        print("\n" + "="*70)
        return result
        
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        return None


def main():
    """Main test function"""
    print_separator("GRAPH RETRIEVAL TESTING")
    
    # Test 1: Depression query
    print_separator("TEST 1: Depression Symptoms")
    test_query("I'm feeling extremely frustrated because my friend keeps ignoring my boundaries. What can I do to calm myself down?")
    
    # Test 2: Anxiety query
    print_separator("TEST 2: Anxiety Management")
    test_query("My coworker is acting childish, and it's making me really frustrated. How should I handle this situation?")
    
    # Test 3: Stress query
    print_separator("TEST 3: Stress Causes")
    test_query("I'm overwhelmed with frustration after arguing with my family today. What would help me feel better?")
    
    # Test 4: PTSD query
    print_separator("TEST 4: PTSD Information")
    test_query("I feel frustrated and helpless because my friend won’t listen. What steps can I take to respond more constructively?")
    
    # Test 5: Custom parameters
    print_separator("TEST 5: Custom Parameters")
    test_query(
        "I’m so frustrated that I can’t focus on anything. What coping strategies should I try right now?"
    )
    
    # # Test 6: No matches query
    # print_separator("TEST 6: No Matches Query")
    # test_query("xyzabc random nonsense query 12345")
    
    # # Test 7: Mental health treatment
    # print_separator("TEST 7: Treatment Options")
    # test_query("What are treatment options for mental health issues?")
    
    # # Test 8: Low threshold (more results)
    # print_separator("TEST 8: Low Threshold Test")
    # test_query(
    #     "How to deal with sadness?",
    #     milvus_threshold=0.6,
    #     rerank_top_k=5
    # )
    
    print_separator("ALL TESTS COMPLETED")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user\n")
    except Exception as e:
        print(f"\n\n[X] Fatal error: {e}\n")
        import traceback
        traceback.print_exc()