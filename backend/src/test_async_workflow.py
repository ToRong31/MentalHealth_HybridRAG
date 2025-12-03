"""
Async Workflow Testing Script
Test the async LangGraph workflow with parallel retrieval
Run: python3 -m src.test_async_workflow
"""
import asyncio
import time
from src.rag.workflow.workflow import build_kg_graph


def print_separator(title=""):
    """Print a nice separator"""
    print("\n" + "="*70)
    if title:
        print(f"{title}")
        print("="*70)
    print()


async def test_workflow_async(query: str):
    """Test async workflow execution"""
    print(f"Query: {query}")
    print("-" * 70)
    
    # Build workflow
    workflow = build_kg_graph()
    
    # Prepare initial state
    initial_state = {
        "question": query
    }
    
    start_time = time.time()
    
    # Invoke workflow asynchronously
    result = await workflow.ainvoke(initial_state)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n[Workflow Results]")
    print(f"  Execution time: {elapsed_time:.2f}s")
    print(f"  Language: {result.get('user_language', 'N/A')}")
    print(f"  Mental health related: {result.get('is_mental_health_related', 'N/A')}")
    print(f"  High risk: {result.get('is_high_risk', 'N/A')}")
    
    if result.get('retrieval_metadata'):
        meta = result['retrieval_metadata']
        print(f"  Retrieval time: {meta.get('execution_time', 0):.2f}s")
    
    print(f"\n[Answer]")
    answer = result.get('answer', 'No answer generated')
    print(answer[:500] + "..." if len(answer) > 500 else answer)
    
    return result, elapsed_time


async def test_concurrent_requests():
    """Test multiple concurrent workflow requests"""
    print_separator("CONCURRENT WORKFLOW REQUESTS")
    
    queries = [
        "I'm feeling extremely frustrated. What can I do?",
        "How do I handle anxiety?",
        "I'm stressed about work.",
    ]
    
    print(f"Running {len(queries)} concurrent workflow requests...\n")
    
    start_time = time.time()
    
    # Run all workflows concurrently
    tasks = [test_workflow_async(q) for q in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed_time = time.time() - start_time
    
    print(f"\n[Concurrent Execution Summary]")
    print(f"  Total queries: {len(queries)}")
    print(f"  Total time: {elapsed_time:.2f}s")
    print(f"  Average time per query: {elapsed_time/len(queries):.2f}s")
    
    # Check for errors
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        print(f"  Errors: {len(errors)}")
        for err in errors:
            print(f"    - {err}")
    else:
        print(f"  All requests completed successfully!")


async def main():
    """Main test function"""
    print_separator("ASYNC WORKFLOW TESTING")
    
    # Test 1: Single workflow execution
    print_separator("TEST 1: Single Workflow Execution")
    await test_workflow_async(
        "I'm feeling extremely frustrated because my friend keeps ignoring my boundaries. What can I do to calm myself down?"
    )
    
    # Test 2: Vietnamese query
    print_separator("TEST 2: Vietnamese Query")
    await test_workflow_async(
        "Tôi cảm thấy rất căng thẳng và lo lắng. Tôi nên làm gì?"
    )
    
    # Test 3: Concurrent requests
    await test_concurrent_requests()
    
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
