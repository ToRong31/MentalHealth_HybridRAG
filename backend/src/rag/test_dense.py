"""
Test Dense Retrieval with Detailed Scores and LLM Response
Run: python3 -m src.rag.test_dense
"""

import sys
import time
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add backend src to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.rag.vectors.dense_retriever import DenseRetriever
from src.rag.reranker.reranker import CohereReranker
from src.rag.llm.llm_gemini import LLMClient


def print_separator(title=""):
    """Print a separator line with optional title."""
    if title:
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    else:
        print(f"\n{'-'*80}\n")


def load_vietnamese_prompt():
    """Load Vietnamese prompt template from YAML"""
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / "answer_nodes_prompt_vie.yaml"
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('system_instructions', ''), data.get('user_template', '')


def format_prompt(system_instructions: str, user_template: str, question: str, graph_context: str) -> str:
    """Format the full prompt"""
    user_content = user_template.replace("{{QUESTION}}", question).replace("{{GRAPH_CONTEXT}}", graph_context)
    full_prompt = f"{system_instructions}\n\n{user_content}"
    return full_prompt


def test_detailed_dense_retrieval():
    """
    Test dense retrieval with detailed scores:
    - Top 10 from Milvus
    - Top 3 after rerank
    - Top 3 chunks with full context
    - LLM response with Vietnamese prompt
    """
    print_separator("🚀 DENSE RETRIEVAL WITH DETAILED SCORES & LLM RESPONSE")
    
    # Test query (Vietnamese)
    query = "I am feeling very angry because my friend keeps ignoring my boundaries. What can I do to calm down?"
    
    print(f"📝 Query: {query}\n")
    print("="*80)
    
    # Initialize components
    dense_retriever = DenseRetriever(collection_name="clinicalbook")
    reranker = CohereReranker()
    milvus_top_k = 10
    rerank_top_k = 3
    
    # ===== STEP 1: Milvus Retrieval (Top 10) =====
    print("\n🔍 STEP 1: Milvus Dense Retrieval (Top 10)")
    print("-" * 80)
    
    milvus_results: List[List[Tuple[int, float]]] = dense_retriever.retrieve(
        [query],
        top_k=milvus_top_k,
    )
    candidates_for_query = milvus_results[0]
    
    print(f"\n📊 Top {len(candidates_for_query)} Results from Milvus:\n")
    for rank, (node_id, score) in enumerate(candidates_for_query, 1):
        print(f"  {rank:2d}. Node ID: {node_id:6d} | Score: {score:.6f}")
    
    # ===== STEP 2: Reranking with Cohere (Top 3) =====
    print("\n" + "="*80)
    print("\n🎯 STEP 2: Cohere Reranking (Top 3)")
    print("-" * 80)
    
    candidates_dicts: List[Dict[str, Any]] = []
    for chunk_id, score in candidates_for_query:
        # Get full text content for reranking
        text_content = dense_retriever.get_dense_context_by_id(chunk_id)
        candidates_dicts.append({
            "chunk_id": chunk_id,
            "original_milvus_score": float(score),
            "text": text_content,  # Add full text for Cohere reranking
        })
    
    reranked = reranker.rerank_chunks(
        query=query,
        candidates=candidates_dicts,
        top_k=rerank_top_k,
    )
    
    print(f"\n📊 Top {len(reranked)} Results after Reranking:\n")
    for rank, c in enumerate(reranked, 1):
        chunk_id = c["chunk_id"]
        cohere_score = c["cohere_score"]
        milvus_score = c["original_milvus_score"]
        print(f"  {rank}. Chunk ID: {chunk_id:6d} | Cohere Score: {cohere_score:.6f} | Milvus Score: {milvus_score:.6f}")
    
    # ===== STEP 3: Get Full Context for Top 3 =====
    print("\n" + "="*80)
    print("\n📄 STEP 3: Full Context of Top 3 Chunks")
    print("-" * 80)
    
    dense_context_parts = []
    for rank, c in enumerate(reranked, 1):
        chunk_id = c["chunk_id"]
        cohere_score = c["cohere_score"]
        answer_text = dense_retriever.get_dense_context_by_id(chunk_id)
        
        print(f"\n[Chunk {rank}] Chunk ID: {chunk_id} | Score: {cohere_score:.6f}")
        print(f"{'─' * 80}")
        print(answer_text)
        print(f"{'─' * 80}")
        
        dense_context_parts.append(
            f"Answer (ID: {chunk_id}, Score: {cohere_score:.4f}): {answer_text}"
        )
    
    dense_context = "\n".join(dense_context_parts)
    
    # ===== STEP 4: Generate LLM Response =====
    print("\n" + "="*80)
    print("\n🤖 STEP 4: Generate LLM Response (Vietnamese)")
    print("-" * 80)
    
    # Load Vietnamese prompt
    system_instructions, user_template = load_vietnamese_prompt()
    
    # Format prompt
    full_prompt = format_prompt(system_instructions, user_template, query, dense_context)
    
    print(f"\n📝 Prompt Length: {len(full_prompt)} chars")
    print("\n⏳ Calling LLM...")
    
    # Call LLM
    llm_client = LLMClient()
    start_time = time.time()
    response = llm_client.invoke(full_prompt)
    elapsed_time = time.time() - start_time
    
    print(f"✅ Response generated in {elapsed_time:.2f}s")
    print("\n" + "="*80)
    print("\n💬 LLM RESPONSE:")
    print("-" * 80)
    print(response)
    print("\n" + "="*80)
    
    return response


def test_single_query():
    """
    Test a single query for quick testing.
    """
    print_separator("SINGLE QUERY TEST - CLINICALBOOK (TREATMENT)")
    
    # Initialize Dense Retrieval
    print("🔧 Initializing DenseRetrieval...")
    dense_retrieval = DenseRetrieval(
        collection_name="clinicalbook",
        milvus_top_k=20,
    )
    print("✅ Initialized!\n")
    
    # Test query focused on treatment
    query = "What are the most effective treatment interventions for alcohol problems?"
    print(f"📝 Query: {query}\n")
    
    # Retrieve
    result = dense_retrieval.retrieve(query=query, top_k=5)
    
    # Display results
    print("🎯 Retrieved Context:\n")
    print(result.context)
    print(f"\n📊 Metadata: {result.metadata}")
    
    print_separator("TEST COMPLETED")


def test_different_top_k():
    """
    Test with different top_k values to see how results vary.
    """
    print_separator("TOP-K COMPARISON TEST")
    
    # Initialize Dense Retrieval
    print("🔧 Initializing DenseRetrieval...")
    dense_retrieval = DenseRetrieval(
        collection_name="clinicalbook",
        milvus_top_k=20,
    )
    print("✅ Initialized!\n")
    
    query = "What treatment strategies help overcome alcohol addiction?"
    print(f"📝 Query: {query}\n")
    
    # Test with different top_k values
    for k in [1, 2, 3, 5]:
        print(f"\n{'='*40}")
        print(f"  TOP-K = {k}")
        print(f"{'='*40}\n")
        
        result = dense_retrieval.retrieve(query=query, top_k=k)
        print(result.context)
        print()
    
    print_separator("COMPARISON TEST COMPLETED")


def test_with_milvus_parameters():
    """
    Test with different Milvus top_k parameters.
    """
    print_separator("MILVUS TOP-K PARAMETER TEST")
    
    query = "How to implement cognitive behavioral treatment for alcohol disorders?"
    print(f"📝 Query: {query}\n")
    
    # Test with different milvus_top_k values
    for milvus_k in [10, 20, 30]:
        print(f"\n{'='*40}")
        print(f"  Milvus TOP-K = {milvus_k}")
        print(f"{'='*40}\n")
        
        dense_retrieval = DenseRetrieval(
            collection_name="clinicalbook",
            milvus_top_k=milvus_k,
        )
        
        result = dense_retrieval.retrieve(query=query, top_k=3)
        print(result.context)
        print()
    
    print_separator("PARAMETER TEST COMPLETED")


def test_treatment_focused_queries():
    """
    Test specific treatment-focused queries with detailed output.
    """
    print_separator("TREATMENT-FOCUSED DETAILED TEST")
    
    # Initialize Dense Retrieval
    print("🔧 Initializing DenseRetrieval...")
    dense_retrieval = DenseRetrieval(
        collection_name="clinicalbook",
        milvus_top_k=20,
    )
    print("✅ Initialized!\n")
    
    # Specific treatment queries
    treatment_queries = [
        "behavioral therapy techniques for alcohol treatment",
        "psychotherapy interventions alcohol dependence",
        "clinical strategies treating drinking problems",
        "therapeutic tools alcohol use disorder treatment",
        "counseling methods alcohol abuse recovery"
    ]
    
    for idx, query in enumerate(treatment_queries, 1):
        print(f"\n{'='*60}")
        print(f"  Query {idx}: {query}")
        print(f"{'='*60}\n")
        
        result = dense_retrieval.retrieve(query=query, top_k=3)
        
        print("📄 Retrieved Documents:\n")
        print(result.context)
        
        print(f"\n📈 Scores and IDs:")
        for meta in result.metadata:
            print(f"  - ID: {meta['id']}, Score: {meta['score']:.4f}")
        
        print()
    
    print_separator("TREATMENT-FOCUSED TEST COMPLETED")


if __name__ == "__main__":
    """
    Main execution - Test dense retrieval with detailed scores and LLM response
    """
    try:
        test_detailed_dense_retrieval()
        print_separator("✅ TEST COMPLETED")
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user\n")
    except Exception as e:
        print(f"\n\n[X] Fatal error: {e}\n")
        import traceback
        traceback.print_exc()