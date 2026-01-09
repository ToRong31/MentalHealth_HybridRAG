"""
Test query rewriter and retrieval effectiveness
"""
import sys
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
from rag.config import rag_settings
from rag.llm.gemini_client import GeminiClient
from rag.prompts.prompt_loader import load_query_rewrite_prompt

print("="*80)
print("🔍 TESTING QUERY REWRITER & RETRIEVAL")
print("="*80)

# Test cases - Vietnamese queries
test_queries = [
    {
        "original": "Tôi hay giật mình và có cảm giác không thoải mái trước khi làm điều gì đó",
        "slots": {
            "physical_symptoms": ["giật mình", "cảm giác không thoải mái"],
            "timing": ["trước khi làm điều gì đó"]
        },
        "expected_disease": "Tic Disorders"
    },
    {
        "original": "Con tôi hay nhấp nháy mắt và khạc khạc họng",
        "slots": {
            "physical_symptoms": ["nhấp nháy mắt", "khạc họng"],
            "age": ["child"]
        },
        "expected_disease": "Tic Disorders"
    },
    {
        "original": "Tôi có cảm giác buộc phải làm một động tác nhiều lần cho đến khi cảm thấy đúng",
        "slots": {
            "compulsion": ["làm lại nhiều lần"],
            "mental_state": ["cảm giác buộc phải", "cho đến khi đúng"]
        },
        "expected_disease": "Tic Disorders / OCD"
    },
]

try:
    # Load models
    print("📦 Loading models...")
    model = SentenceTransformer(rag_settings.E5_MODEL_NAME)
    gemini = GeminiClient()
    prompt_template = load_query_rewrite_prompt()
    print("✅ Models loaded\n")
    
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus\n")
    
    collection_name = "mental_health_diagnostic_support"
    
    for i, test_case in enumerate(test_queries, 1):
        print("="*80)
        print(f"TEST CASE #{i}")
        print("="*80)
        print(f"Original Query (Vietnamese): {test_case['original']}")
        print(f"Extracted Slots: {test_case['slots']}")
        print(f"Expected Disease: {test_case['expected_disease']}")
        print()
        
        # 1. Rewrite query
        print("🔄 Rewriting query...")
        slot_context = "\n".join([f"- {k}: {v}" for k, v in test_case['slots'].items()])
        
        filled_prompt = prompt_template.replace("{{ORIGINAL_QUESTION}}", test_case['original'])
        filled_prompt = filled_prompt.replace("{{SLOT_CONTEXT}}", slot_context)
        filled_prompt = filled_prompt.replace("{{CONVERSATION_BUFFER}}", "(empty)")
        filled_prompt = filled_prompt.replace("{{CONVERSATION_SUMMARY}}", "(empty)")
        
        rewritten_query = gemini.generate_text(filled_prompt, max_tokens=200)
        print(f"✅ Rewritten Query:\n{rewritten_query}")
        print()
        
        # 2. Test retrieval with ORIGINAL query
        print("🔍 Testing retrieval with ORIGINAL Vietnamese query...")
        original_embedding = model.encode([f"query: {test_case['original']}"])[0].tolist()
        original_results = client.search(
            collection_name=collection_name,
            data=[original_embedding],
            limit=5,
            output_fields=["node_id", "disease"],
            search_params={"metric_type": "COSINE", "params": {}}
        )
        
        print("Top 5 results (Original):")
        for j, hit in enumerate(original_results[0], 1):
            print(f"  {j}. Disease: {hit['entity'].get('disease')} | Score: {hit['distance']:.4f} | Node: {hit['entity'].get('node_id')}")
        print()
        
        # 3. Test retrieval with REWRITTEN query
        print("🔍 Testing retrieval with REWRITTEN query...")
        rewritten_embedding = model.encode([f"query: {rewritten_query}"])[0].tolist()
        rewritten_results = client.search(
            collection_name=collection_name,
            data=[rewritten_embedding],
            limit=5,
            output_fields=["node_id", "disease"],
            search_params={"metric_type": "COSINE", "params": {}}
        )
        
        print("Top 5 results (Rewritten):")
        for j, hit in enumerate(rewritten_results[0], 1):
            print(f"  {j}. Disease: {hit['entity'].get('disease')} | Score: {hit['distance']:.4f} | Node: {hit['entity'].get('node_id')}")
        print()
        
        # 4. Analysis
        original_has_expected = any(test_case['expected_disease'] in hit['entity'].get('disease', '') 
                                    for hit in original_results[0][:3])
        rewritten_has_expected = any(test_case['expected_disease'] in hit['entity'].get('disease', '') 
                                     for hit in rewritten_results[0][:3])
        
        print("📊 Analysis:")
        print(f"  Original query finds expected disease in top 3: {'✅ YES' if original_has_expected else '❌ NO'}")
        print(f"  Rewritten query finds expected disease in top 3: {'✅ YES' if rewritten_has_expected else '❌ NO'}")
        
        if rewritten_results[0] and original_results[0]:
            improvement = rewritten_results[0][0]['distance'] - original_results[0][0]['distance']
            print(f"  Score improvement: {improvement:+.4f}")
        print()
    
    print("="*80)
    print("✅ TEST COMPLETED")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
