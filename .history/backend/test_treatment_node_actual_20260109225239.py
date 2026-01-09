"""
Test actual treatment retrieval node with real state
"""
import sys
import os
sys.path.insert(0, "/app")

import asyncio
from src.rag.workflow.state import KGState
from src.rag.workflow.graph_nodes.treatment_retrieval import treatment_retrieval_node

print("="*80)
print("🧪 TESTING ACTUAL TREATMENT RETRIEVAL NODE")
print("="*80)
print()

# Create test state with detected disease
test_state = KGState(
    question="Cách điều trị trầm cảm?",
    rewritten_query="Cách điều trị rối loạn trầm cảm?",
    disease_detected=["Depressive Disorders"],
    detected_disease="Depressive Disorders",
    treatment_chunks=[],
    treatment_node_ids=[]
)

print("📝 Input state:")
print(f"  Question: {test_state['question']}")
print(f"  Rewritten query: {test_state['rewritten_query']}")
print(f"  Disease detected: {test_state['disease_detected']}")
print()

async def run_test():
    print("🚀 Running treatment_retrieval_node...")
    print("-" * 80)
    
    result_state = await treatment_retrieval_node(test_state)
    
    print()
    print("="*80)
    print("📊 RESULTS")
    print("="*80)
    
    treatment_chunks = result_state.get("treatment_chunks", [])
    treatment_node_ids = result_state.get("treatment_node_ids", [])
    
    print(f"\n✅ Retrieved {len(treatment_chunks)} treatment chunks")
    print(f"✅ Node IDs: {len(treatment_node_ids)}")
    
    if treatment_chunks:
        print(f"\n📚 First 3 chunks:")
        for i, chunk in enumerate(treatment_chunks[:3], 1):
            print(f"\n--- Chunk {i} ---")
            print(f"Title: {chunk.get('title', 'N/A')}")
            print(f"Text preview: {chunk.get('text', '')[:200]}...")
    else:
        print("\n❌ NO TREATMENT CHUNKS RETRIEVED!")
        print("This is the main problem!")
    
    if treatment_node_ids:
        print(f"\n🔢 Node IDs: {treatment_node_ids[:5]}...")
    
    return len(treatment_chunks) > 0

# Run the test
success = asyncio.run(run_test())

print()
print("="*80)
if success:
    print("✅ TEST PASSED: Treatment retrieval working!")
    sys.exit(0)
else:
    print("❌ TEST FAILED: No treatment chunks retrieved")
    sys.exit(1)
