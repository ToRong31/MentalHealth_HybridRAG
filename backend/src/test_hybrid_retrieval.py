"""
Test Hybrid Retrieval Performance
Compare sequential vs hybrid (parallel) retrieval execution times
Run: python3 -m src.test_hybrid_retrieval
"""
import asyncio
import time
from src.rag.retrieval.hybrid_retriever import hybrid_retriever
from src.rag.retrieval.graph_retrieval import graph_retrieval
from src.rag.retrieval.dense_retrieval import dense_retrieval


def print_separator(title=""):
    """Print a nice separator"""
    print("\n" + "="*70)
    if title:
        print(f"{title}")
        print("="*70)
    print()


async def test_hybrid_retrieval(query: str):
    """Test hybrid retrieval and measure execution time"""
    print(f"Query: {query}")
    print("-" * 70)
    
    start_time = time.time()
    result = await hybrid_retriever.retrieve_async(query)
    elapsed_time = time.time() - start_time
    
    print(f"\n[Hybrid Retrieval Results]")
    print(f"  Execution time: {elapsed_time:.2f}s")
    print(f"  Context length: {len(result.context)} chars")
    print(f"  Metadata: {result.metadata.get('execution_time', 0):.2f}s")
    
    # Print graph metadata
    graph_meta = result.metadata.get('graph_metadata', {})
    print(f"\n[Graph Retrieval]")
    print(f"  Anchors: {len(graph_meta.get('anchors', []))}")
    print(f"  Nodes: {graph_meta.get('nodes_count', 0)}")
    print(f"  Relationships: {graph_meta.get('rels_count', 0)}")
    
    # Print dense metadata
    dense_meta = result.metadata.get('dense_metadata', {})
    print(f"\n[Dense Retrieval]")
    print(f"  Source: {dense_meta.get('source', 'N/A')}")
    
    # Print context lengths
    print(f"\n[Context Lengths]")
    print(f"  Graph context: {result.metadata.get('graph_context_length', 0)} chars")
    print(f"  Dense context: {result.metadata.get('dense_context_length', 0)} chars")
    print(f"  Combined total: {len(result.context)} chars")
    
    print(f"\n[Full Combined Context]")
    print(result.context)  # Display full context
    print("\n" + "="*70)
    
    return result, elapsed_time


async def test_sequential_retrieval(query: str):
    """Test sequential retrieval for comparison"""
    print(f"Query: {query}")
    print("-" * 70)
    
    start_time = time.time()
    
    # Run sequentially
    graph_result = await graph_retrieval.retrieve_async(query)
    dense_result = await dense_retrieval.retrieve_async(query, top_k=2)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n[Sequential Retrieval Results]")
    print(f"  Execution time: {elapsed_time:.2f}s")
    print(f"  Graph context: {len(graph_result.context)} chars")
    print(f"  Dense context: {len(dense_result.context)} chars")
    
    return elapsed_time


async def compare_performance(query: str):
    """Compare hybrid vs sequential performance"""
    print_separator("PERFORMANCE COMPARISON")
    
    print("\n🔄 Running HYBRID retrieval...")
    hybrid_result, hybrid_time = await test_hybrid_retrieval(query)
    
    print("\n" + "="*70)
    print("\n⏭️  Running SEQUENTIAL retrieval...")
    sequential_time = await test_sequential_retrieval(query)
    
    print("\n" + "="*70)
    print("\n📊 PERFORMANCE SUMMARY")
    print(f"  Hybrid time:     {hybrid_time:.2f}s")
    print(f"  Sequential time: {sequential_time:.2f}s")
    speedup = sequential_time / hybrid_time if hybrid_time > 0 else 0
    print(f"  Speedup:         {speedup:.2f}x")
    print(f"  Time saved:      {sequential_time - hybrid_time:.2f}s")


async def main():
    """Main test function"""
    print_separator("HYBRID RETRIEVAL TESTING")
    
    test_queries = [
        "I'm feeling extremely frustrated because my friend keeps ignoring my boundaries. What can I do to calm myself down?",
        "My coworker is acting childish, and it's making me really frustrated. How should I handle this situation?",
        "I'm overwhelmed with frustration after arguing with my family today. What would help me feel better?",
    ]
    
    # Test 1: Performance comparison
    await compare_performance(test_queries[0])
    
    # Test 2: Multiple hybrid retrievals
    print_separator("MULTIPLE HYBRID RETRIEVALS")
    for i, query in enumerate(test_queries[1:], 2):
        print(f"\nTest {i}:")
        await test_hybrid_retrieval(query)
    
    print_separator("ALL TESTS COMPLETED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user\n")
    except Exception as e:
        print(f"\n\n[X] Fatal error: {e}\n")
        import traceback
        traceback.print_exc()
