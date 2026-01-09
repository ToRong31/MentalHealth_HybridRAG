"""
Test Query Rewriter Prompt - Check Retrieval Effectiveness
Compare retrieval quality before and after query rewriting
"""
import sys
import json
sys.path.insert(0, "/app/src")

from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer
from rag.config import rag_settings
from rag.llm.llm_gemini import llm
from rag.prompts.loader import load_prompts, format_prompt

print("="*80)
print("🧪 TESTING QUERY REWRITER PROMPT")
print("="*80)

# Test cases covering diverse disorders
test_cases = [
    {
        "id": 1,
        "category": "Depression",
        "vietnamese": "Tôi buồn và mệt mỏi suốt 2 tuần",
        "slots": {
            "emotion": ["buồn"],
            "fatigue": ["mệt mỏi"],
            "duration": ["2 tuần"]
        },
        "expected_diseases": ["Major Depressive Disorder", "Depressive", "Depression"]
    },
    {
        "id": 2,
        "category": "Anxiety",
        "vietnamese": "Tôi lo lắng liên tục, khó kiểm soát",
        "slots": {
            "emotion": ["lo lắng"],
            "pattern": ["liên tục"],
            "control": ["khó kiểm soát"]
        },
        "expected_diseases": ["Generalized Anxiety", "Anxiety Disorder"]
    },
    {
        "id": 3,
        "category": "OCD",
        "vietnamese": "Tôi phải rửa tay nhiều lần mới yên tâm",
        "slots": {
            "compulsion": ["rửa tay nhiều lần"],
            "anxiety": ["không yên tâm"]
        },
        "expected_diseases": ["Obsessive-Compulsive", "OCD"]
    },
    {
        "id": 4,
        "category": "Panic",
        "vietnamese": "Tôi hay bị cơn hồi hộp, khó thở đột ngột",
        "slots": {
            "physical": ["hồi hộp", "khó thở"],
            "onset": ["đột ngột"]
        },
        "expected_diseases": ["Panic", "Anxiety"]
    },
    {
        "id": 5,
        "category": "PTSD",
        "vietnamese": "Sau tai nạn, tôi hay giật mình và tránh đi qua chỗ đó",
        "slots": {
            "trigger": ["sau tai nạn"],
            "symptoms": ["giật mình", "tránh"]
        },
        "expected_diseases": ["PTSD", "Acute Stress", "Trauma"]
    },
    {
        "id": 6,
        "category": "Tic Disorders",
        "vietnamese": "Con tôi hay nhấp nháy mắt và khạc họng",
        "slots": {
            "physical_symptoms": ["nhấp nháy mắt", "khạc họng"],
            "age": ["child"]
        },
        "expected_diseases": ["Tic", "Tourette"]
    },
]

try:
    # Load components
    print("📦 Loading components...")
    model = SentenceTransformer(rag_settings.E5_MODEL_NAME)
    
    # Load rewriter prompt
    rewriter_prompts = load_prompts("rewritter_promt.yaml")
    prompt_template = rewriter_prompts.get("query_rewrite_prompt", "")
    
    if not prompt_template:
        raise ValueError("Failed to load query_rewrite_prompt")
    
    print(f"✅ Loaded prompt (length: {len(prompt_template)} chars)")
    
    # Connect to Milvus
    client = MilvusClient(
        uri=rag_settings.MILVUS_URI,
        token=rag_settings.MILVUS_TOKEN if hasattr(rag_settings, 'MILVUS_TOKEN') else None
    )
    print("✅ Connected to Milvus")
    print()
    
    collection_name = "mental_health_diagnostic_support"
    
    # Statistics tracking
    stats = {
        "total_tests": len(test_cases),
        "original_found": 0,
        "rewritten_found": 0,
        "improvements": 0,
        "score_improvements": []
    }
    
    for test in test_cases:
        print("="*80)
        print(f"TEST CASE #{test['id']}: {test['category']}")
        print("="*80)
        print(f"Vietnamese Query: {test['vietnamese']}")
        print(f"Expected Diseases: {', '.join(test['expected_diseases'])}")
        print()
        
        # Build slot context
        slot_context = "\n".join([f"- {k}: {v}" for k, v in test['slots'].items()])
        
        # 1. REWRITE QUERY
        print("🔄 Step 1: Rewriting query...")
        filled_prompt = format_prompt(
            prompt_template,
            ORIGINAL_QUESTION=test['vietnamese'],
            SLOT_CONTEXT=slot_context,
            CONVERSATION_BUFFER="(empty)",
            CONVERSATION_SUMMARY="(empty)"
        )
        
        rewritten_query = llm.generate_text(filled_prompt, max_tokens=250)
        print(f"✅ Rewritten Query:\n{rewritten_query}\n")
        
        # 2. TEST RETRIEVAL WITH ORIGINAL VIETNAMESE
        print("🔍 Step 2: Retrieval with ORIGINAL Vietnamese query...")
        original_embedding = model.encode([f"query: {test['vietnamese']}"])[0].tolist()
        original_results = client.search(
            collection_name=collection_name,
            data=[original_embedding],
            limit=5,
            output_fields=["node_id", "disease"],
            search_params={"metric_type": "COSINE", "params": {}}
        )
        
        print("Top 5 Results (Original):")
        original_found = False
        for i, hit in enumerate(original_results[0][:5], 1):
            disease = hit['entity'].get('disease', 'Unknown')
            score = hit['distance']
            print(f"  {i}. {disease:40s} | Score: {score:.4f}")
            
            # Check if expected disease found in top 3
            if i <= 3:
                for expected in test['expected_diseases']:
                    if expected.lower() in disease.lower():
                        original_found = True
                        break
        
        original_top_score = original_results[0][0]['distance'] if original_results[0] else 0
        print()
        
        # 3. TEST RETRIEVAL WITH REWRITTEN QUERY
        print("🔍 Step 3: Retrieval with REWRITTEN English query...")
        rewritten_embedding = model.encode([f"query: {rewritten_query}"])[0].tolist()
        rewritten_results = client.search(
            collection_name=collection_name,
            data=[rewritten_embedding],
            limit=5,
            output_fields=["node_id", "disease"],
            search_params={"metric_type": "COSINE", "params": {}}
        )
        
        print("Top 5 Results (Rewritten):")
        rewritten_found = False
        for i, hit in enumerate(rewritten_results[0][:5], 1):
            disease = hit['entity'].get('disease', 'Unknown')
            score = hit['distance']
            print(f"  {i}. {disease:40s} | Score: {score:.4f}")
            
            # Check if expected disease found in top 3
            if i <= 3:
                for expected in test['expected_diseases']:
                    if expected.lower() in disease.lower():
                        rewritten_found = True
                        break
        
        rewritten_top_score = rewritten_results[0][0]['distance'] if rewritten_results[0] else 0
        print()
        
        # 4. ANALYSIS
        print("📊 Analysis:")
        print(f"  Original found expected disease in top 3: {'✅ YES' if original_found else '❌ NO'}")
        print(f"  Rewritten found expected disease in top 3: {'✅ YES' if rewritten_found else '❌ NO'}")
        
        score_diff = rewritten_top_score - original_top_score
        print(f"  Top score change: {score_diff:+.4f} ({original_top_score:.4f} → {rewritten_top_score:.4f})")
        
        if rewritten_found and not original_found:
            print("  🎯 IMPROVEMENT: Rewriter found relevant disease!")
            stats["improvements"] += 1
        elif original_found and not rewritten_found:
            print("  ⚠️  REGRESSION: Original was better")
        elif rewritten_found and original_found:
            if score_diff > 0.01:
                print("  📈 SCORE IMPROVEMENT: Higher relevance score")
            else:
                print("  ✅ MAINTAINED: Both found disease")
        else:
            print("  ⚠️  MISS: Neither found expected disease")
        
        # Update stats
        if original_found:
            stats["original_found"] += 1
        if rewritten_found:
            stats["rewritten_found"] += 1
        stats["score_improvements"].append(score_diff)
        
        print()
    
    # FINAL SUMMARY
    print("="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    print(f"Total Test Cases: {stats['total_tests']}")
    print()
    print(f"Original Query Performance:")
    print(f"  Found expected disease: {stats['original_found']}/{stats['total_tests']} ({stats['original_found']/stats['total_tests']*100:.1f}%)")
    print()
    print(f"Rewritten Query Performance:")
    print(f"  Found expected disease: {stats['rewritten_found']}/{stats['total_tests']} ({stats['rewritten_found']/stats['total_tests']*100:.1f}%)")
    print()
    print(f"Improvement Cases: {stats['improvements']}")
    
    avg_score_improvement = sum(stats["score_improvements"]) / len(stats["score_improvements"])
    print(f"Average Score Change: {avg_score_improvement:+.4f}")
    
    # Verdict
    print()
    print("="*80)
    if stats["rewritten_found"] > stats["original_found"]:
        print("✅ VERDICT: Query Rewriter IMPROVES retrieval effectiveness!")
        print(f"   Improvement: +{stats['rewritten_found'] - stats['original_found']} cases")
    elif stats["rewritten_found"] == stats["original_found"]:
        if avg_score_improvement > 0:
            print("✅ VERDICT: Query Rewriter MAINTAINS performance with BETTER scores")
        else:
            print("⚠️  VERDICT: Query Rewriter MAINTAINS performance (no change)")
    else:
        print("❌ VERDICT: Query Rewriter REDUCES retrieval effectiveness")
        print(f"   Regression: -{stats['original_found'] - stats['rewritten_found']} cases")
    print("="*80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
