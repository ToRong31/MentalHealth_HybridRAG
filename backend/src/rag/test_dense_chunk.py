"""
Test Dense Retrieval with Slot Filling and Vietnamese Translation
Tests the complete pipeline: Vietnamese question -> Slot Filling -> Translation -> Retrieval -> Response

Run: python3 -m src.rag.test_dense_chunk
"""

import sys
import time
import asyncio
import yaml
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add backend src to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.rag.vectors.dense_retriever import DenseRetriever
from src.rag.reranker.reranker import CohereReranker
from src.rag.llm.llm_gemini import LLMClient
from src.rag.llm.answer_nodes.slot_filling import process_slot_filling
from src.rag.llm.translator import GeminiTranslator


def print_separator(title="", symbol="="):
    """Print a separator line with optional title."""
    if title:
        print(f"\n{symbol*80}")
        print(f"  {title}")
        print(f"{symbol*80}\n")
    else:
        print(f"\n{symbol*80}\n")


def print_slots_summary(slots_data: Dict[str, Any]):
    """Print a summary of extracted slots"""
    slots = slots_data.get("slots", {})
    missing_slots = slots_data.get("missing_slots", [])
    relevant_missing = slots_data.get("relevant_missing_slots", [])
    follow_ups = slots_data.get("follow_up_questions", [])
    
    # Count filled slots
    filled_slots = {k: v for k, v in slots.items() if v is not None and v != [] and v != "none"}
    
    print(f"✅ Filled Slots: {len(filled_slots)}")
    if filled_slots:
        for key, value in filled_slots.items():
            if isinstance(value, list):
                value_str = ", ".join(str(v) for v in value) if value else "[]"
            else:
                value_str = str(value)
            print(f"   • {key}: {value_str}")
    
    print(f"\n❌ Missing Slots: {len(missing_slots)}")
    if missing_slots:
        print(f"   {', '.join(missing_slots)}")
    
    print(f"\n🎯 Relevant Missing Slots: {len(relevant_missing)}")
    if relevant_missing:
        print(f"   {', '.join(relevant_missing)}")
    
    print(f"\n💬 Follow-up Questions: {len(follow_ups)}")
    if follow_ups:
        for i, q in enumerate(follow_ups, 1):
            print(f"   {i}. {q}")


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


async def test_complete_pipeline():
    """
    Test the complete pipeline:
    1. Vietnamese question -> Slot Filling
    2. Translate question to English
    3. Dense retrieval (Milvus + Rerank)
    4. Display retrieved chunks
    """
    print_separator("🚀 DENSE CHUNK TEST: SLOT FILLING + TRANSLATION + RETRIEVAL")
    
    # Vietnamese test query
    vietnamese_query = "Dạo này mình cảm thấy rất lo lắng khi đi làm, cứ tới gần giờ vào công ty là trong người bồn chồn khó chịu. Mình không biết phải làm sao."
    
    print(f"📝 Original Question (Vietnamese):\n{vietnamese_query}\n")
    
    # ===== STEP 1: SLOT FILLING =====
    print_separator("STEP 1: SLOT FILLING", "-")
    print("⏳ Extracting slots from Vietnamese question...\n")
    
    start_time = time.time()
    slots_data = await process_slot_filling(vietnamese_query)
    slot_time = time.time() - start_time
    
    print(f"✅ Slot filling completed in {slot_time:.2f}s\n")
    print_slots_summary(slots_data)
    
    # ===== STEP 2: TRANSLATE QUESTION =====
    print_separator("STEP 2: TRANSLATE QUESTION TO ENGLISH", "-")
    print("⏳ Translating question...\n")
    
    translator = GeminiTranslator()
    start_time = time.time()
    english_query = translator.vi_to_en(vietnamese_query)
    translate_time = time.time() - start_time
    
    print(f"✅ Translation completed in {translate_time:.2f}s")
    print(f"\n📝 Translated Question (English):\n{english_query}\n")
    
    # ===== STEP 3: DENSE RETRIEVAL =====
    print_separator("STEP 3: DENSE RETRIEVAL (MILVUS + RERANK)", "-")
    
    # Initialize components
    dense_retriever = DenseRetriever(collection_name="clinicalbook")
    reranker = CohereReranker()
    milvus_top_k = 10
    rerank_top_k = 3
    
    # 3.1: Milvus Retrieval
    print(f"🔍 Retrieving top {milvus_top_k} candidates from Milvus...\n")
    
    start_time = time.time()
    milvus_results: List[List[Tuple[int, float]]] = dense_retriever.retrieve(
        [english_query],
        top_k=milvus_top_k,
    )
    milvus_time = time.time() - start_time
    
    candidates_for_query = milvus_results[0]
    
    print(f"✅ Milvus retrieval completed in {milvus_time:.2f}s")
    print(f"\n📊 Top {len(candidates_for_query)} Results from Milvus:\n")
    for rank, (node_id, score) in enumerate(candidates_for_query, 1):
        print(f"  {rank:2d}. Node ID: {node_id:6d} | Score: {score:.6f}")
    
    # 3.2: Reranking
    print(f"\n🎯 Reranking to top {rerank_top_k}...\n")
    
    candidates_dicts: List[Dict[str, Any]] = []
    for chunk_id, score in candidates_for_query:
        text_content = dense_retriever.get_dense_context_by_id(chunk_id)
        candidates_dicts.append({
            "chunk_id": chunk_id,
            "original_milvus_score": float(score),
            "text": text_content,
        })
    
    start_time = time.time()
    reranked = reranker.rerank_chunks(
        query=english_query,
        candidates=candidates_dicts,
        top_k=rerank_top_k,
    )
    rerank_time = time.time() - start_time
    
    print(f"✅ Reranking completed in {rerank_time:.2f}s")
    print(f"\n📊 Top {len(reranked)} Results after Reranking:\n")
    for rank, c in enumerate(reranked, 1):
        chunk_id = c["chunk_id"]
        cohere_score = c["cohere_score"]
        milvus_score = c["original_milvus_score"]
        print(f"  {rank}. Chunk ID: {chunk_id:6d} | Cohere: {cohere_score:.6f} | Milvus: {milvus_score:.6f}")
    
    # 3.3: Display full chunks
    print("\n📄 Full Content of Retrieved Chunks...\n")
    dense_context_parts = []
    for rank, c in enumerate(reranked, 1):
        chunk_id = c["chunk_id"]
        cohere_score = c["cohere_score"]
        answer_text = dense_retriever.get_dense_context_by_id(chunk_id)
        
        print(f"[Chunk {rank}] ID: {chunk_id} | Score: {cohere_score:.6f}")
        print(f"{'─' * 80}")
        print(answer_text)
        print(f"{'─' * 80}\n")
        
        dense_context_parts.append(
            f"Answer (ID: {chunk_id}, Score: {cohere_score:.4f}): {answer_text}"
        )
    
    dense_context = "\n".join(dense_context_parts)
    
    # ===== FINAL SUMMARY =====
    print_separator("📊 EXECUTION SUMMARY", "=")
    print(f"⏱️  Slot Filling:         {slot_time:.2f}s")
    print(f"⏱️  Question Translation: {translate_time:.2f}s")
    print(f"⏱️  Milvus Retrieval:     {milvus_time:.2f}s")
    print(f"⏱️  Reranking:            {rerank_time:.2f}s")
    print(f"{'─' * 80}")
    total_time = slot_time + translate_time + milvus_time + rerank_time
    print(f"⏱️  TOTAL TIME:           {total_time:.2f}s")
    
    return {
        "slots": slots_data,
        "english_query": english_query,
        "retrieved_chunks": len(reranked),
        "chunks": reranked,
        "timings": {
            "slot_filling": slot_time,
            "question_translation": translate_time,
            "milvus_retrieval": milvus_time,
            "reranking": rerank_time,
            "total": total_time
        }
    }


async def test_multiple_vietnamese_queries():
    """
    Test multiple Vietnamese queries to see how slot filling and translation work
    """
    print_separator("🧪 MULTIPLE VIETNAMESE QUERIES TEST")
    
    test_queries = [
        "Dạo này mình mất ngủ nhiều lắm, ngủ không sâu và sáng dậy rất mệt.",
        "Mình cảm thấy rất buồn và không muốn làm gì cả.",
        "Gần đây mình hay cáu gắt với mọi người xung quanh, mình không biết tại sao.",
        "Mình lo lắng về công việc và không thể tập trung được."
    ]
    
    translator = GeminiTranslator()
    
    for idx, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"  Query {idx}/{len(test_queries)}")
        print(f"{'='*80}\n")
        
        print(f"📝 Vietnamese: {query}\n")
        
        # Slot Filling
        print("⏳ Extracting slots...")
        slots_data = await process_slot_filling(query)
        print_slots_summary(slots_data)
        
        # Translation
        print(f"\n⏳ Translating to English...")
        english_query = translator.vi_to_en(query)
        print(f"✅ English: {english_query}\n")
        
        # Show follow-up questions
        follow_ups = slots_data.get("follow_up_questions", [])
        if follow_ups:
            print("💬 System would ask:")
            for i, q in enumerate(follow_ups, 1):
                print(f"   {i}. {q}")
        
        print()
    
    print_separator("✅ MULTIPLE QUERIES TEST COMPLETED")


async def test_slot_filling_only():
    """
    Quick test for slot filling only (no retrieval)
    """
    print_separator("🔍 SLOT FILLING ONLY TEST")
    
    vietnamese_query = "Mình cảm thấy rất lo lắng và stress, không ngủ được và mệt mỏi suốt ngày."
    
    print(f"📝 Question: {vietnamese_query}\n")
    print("⏳ Processing slot filling...\n")
    
    start_time = time.time()
    slots_data = await process_slot_filling(vietnamese_query)
    elapsed = time.time() - start_time
    
    print(f"✅ Completed in {elapsed:.2f}s\n")
    
    print("=" * 80)
    print("FULL SLOT DETAILS")
    print("=" * 80)
    print(json.dumps(slots_data, indent=2, ensure_ascii=False))
    
    print_separator("✅ TEST COMPLETED")


if __name__ == "__main__":
    """
    Main execution
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Dense Chunk with Slot Filling and Translation")
    parser.add_argument(
        "--test",
        choices=["complete", "multiple", "slots"],
        default="complete",
        help="Test type: complete (full pipeline), multiple (multiple queries), slots (slot filling only)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.test == "complete":
            asyncio.run(test_complete_pipeline())
        elif args.test == "multiple":
            asyncio.run(test_multiple_vietnamese_queries())
        elif args.test == "slots":
            asyncio.run(test_slot_filling_only())
        
        print_separator("✅ ALL TESTS COMPLETED")
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user\n")
    except Exception as e:
        print(f"\n\n[X] Fatal error: {e}\n")
        import traceback
        traceback.print_exc()
