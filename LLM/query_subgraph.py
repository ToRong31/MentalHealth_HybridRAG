# query_subgraph_rag.py
import os
import sys
import json
from typing import List, Dict

# Add parent directory to path to import api_key_manager
from api_key_manager import APIKeyManager, load_api_keys_from_file

from LLM.llm_translate import GeminiTranslator
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
from pymilvus import connections, Collection
from neo4j import GraphDatabase
import torch
import torch.nn.functional as F


from LLM.rerank.cohere import CohereReranker

# ==== 0) CẤU HÌNH GEMINI (LangChain) ====
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import ChatGoogleGenerativeAI


# Load API keys and initialize APIKeyManager
API_KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Input", "api_key.txt")
api_keys = load_api_keys_from_file(API_KEYS_FILE)
answer_key_manager = APIKeyManager(api_keys, min_delay_between_calls=0.2)

# Get first key for initialization (will rotate automatically)
GOOGLE_API_KEY = answer_key_manager.get_next_key()
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.3, google_api_key=GOOGLE_API_KEY)

SYSTEM_INSTRUCTIONS = """
You are a professional mental health counselor having a caring, evidence-based conversation with a patient who trusts you.

CRITICAL RULES:
1. Answer ONLY using the knowledge graph triples provided — do not invent any facts.
2. Write in flowing paragraphs, not bullet points. Sound like a real therapist talking to a patient.
3. Balance empathy with actionable advice (30% validation/empathy, 70% practical solutions).
4. Use confident, professional language as a therapist would:
   - "This approach will help you..."
   - "I recommend trying..."
   - "Deep breathing is effective for..."
   - Avoid tentative phrases: "might", "maybe", "could possibly"

5. If the triples are insufficient to provide a meaningful or relevant answer, respond:
   "Based on the information available, I don't know. Could you provide more details about your situation?"

Tone Guidelines:
- Professional but warm
- Direct and clear
- Speak with authority based on clinical knowledge
- Use "you" and "your" to make it personal
- Avoid dramatic or exaggerated language
- If the context is insufficient, respond with the Rule #5 fallback exactly

Structure (natural flowing paragraphs):
Paragraph 1: Validate their emotional experience (1–2 sentences)
Paragraph 2–3: Present evidence-based interventions clearly and confidently
Paragraph 4: Encourage consistent practice with realistic expectations
Final line: List evidence triples used in brackets
"""


prompt = PromptTemplate(
    input_variables=["triples_text", "question", "system"],
    template=(
        "{system}\n\n"
        "### Knowledge Graph Triples\n"
        "{triples_text}\n\n"
        "### Task\n"
        "Write a professional counselor's response that:\n"
        "1. **Opens with validation**: Acknowledge their struggle professionally (1-2 sentences)\n"
        "2. **Presents interventions confidently**: Use direct statements like:\n"
        "   - 'This technique will help you...'\n"
        "   - 'I recommend trying...'\n"
        "   - 'This approach is effective for...'\n"
        "   - NOT: 'might help', 'could possibly', 'incredibly beneficial'\n"
        "3. **Explains mechanisms**: Why these interventions work (based on triples)\n"
        "4. **Sets realistic expectations**: Encourage practice with professional guidance\n\n"
        "Write 3-4 natural paragraphs as a mental health professional would speak.\n"
        "Do NOT use bullet points or numbered lists.\n"
        "Use confident, clear language based on clinical evidence.\n"
        "Do NOT invent information beyond the triples.\n\n"
        "If no actionable advice exists in triples:\n"
        "'Based on the information available, I recommend scheduling a detailed consultation so we can develop a treatment plan tailored to your specific situation.'\n\n"
        "### Question\n"
        "{question}\n\n"
        "### Response Format\n"
        "[3-4 flowing paragraphs in professional counselor's voice]\n\n"
        "[Evidence: list only TARGETS/ALLEVIATES triples used]\n"
    ),
)

def triples_to_context(triples: List[Dict[str, str]]) -> str:
    lines = []
    for t in triples:
        s = t.get("subject", "").strip()
        p = t.get("predicate", "").strip()
        o = t.get("object", "").strip()
        if s and p and o:
            lines.append(f"- {s} {p} {o}")
    return "\n".join(lines) if lines else "(no triples)"

def answer_with_gemini(triples: List[Dict[str, str]], question: str) -> str:
    triples_text = triples_to_context(triples)
    chain = (
        {
            "triples_text": RunnableLambda(lambda _: triples_text),
            "question": RunnableLambda(lambda _: question),
            "system": RunnableLambda(lambda _: SYSTEM_INSTRUCTIONS),
        }
        | prompt
        | llm
    )
    resp = chain.invoke({})
    return resp.content


# ==== 1) MODEL EMBEDDING ====
device = "cuda" if torch.cuda.is_available() else "cpu"

model = SentenceTransformer("intfloat/e5-large-v2").to(device)

# ==== 2) MILVUS ====
connections.connect(
    alias="default",
    uri="https://in03-b3ec3bf1a4be5eb.serverless.aws-eu-central-1.cloud.zilliz.com",
    token="6ed108e8036c9eb92e50b9bff86e0ae657efda8c827ad090e493f601268132189250a4a907338420c87053d8d8fbc156af7e1b25",
    secure=True,
    db_name="default"
)
col = Collection("kg_entities")
col.load()

# ==== 3) NEO4J ====
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "torong31102005"))

MODEL_NAME = "intfloat/e5-large-v2"
device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
e5_model  = AutoModel.from_pretrained(MODEL_NAME).to(device)
e5_model.eval()

def average_pool(last_hidden_states, attention_mask):
    last_hidden = last_hidden_states.masked_fill(
        ~attention_mask[..., None].bool(), 0.0
    )
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]

def encode_e5(texts):
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        out = e5_model(**inputs)
        pooled = average_pool(out.last_hidden_state, inputs["attention_mask"])
        normed = F.normalize(pooled, p=2, dim=1)
        return normed.cpu().numpy()


# ✅ Initialize Cohere Reranker
reranker = CohereReranker()

# ✅ Hàm lấy node name từ Neo4j
def get_node_names_from_neo4j(node_ids: List[int]) -> Dict[int, str]:
    """
    Lấy tên của các nodes từ Neo4j dựa vào node_id
    
    Args:
        node_ids: List của node IDs
    
    Returns:
        Dict mapping node_id -> name
    """
    if not node_ids:
        return {}
    
    query = """
    MATCH (n:Entity) WHERE n.id IN $ids
    RETURN n.id AS node_id, n.name AS name
    """
    
    with driver.session() as session:
        result = session.run(query, {"ids": node_ids})
        node_map = {}
        for record in result:
            node_id = record["node_id"]
            name = record["name"] or f"Node_{node_id}"
            node_map[node_id] = name
        
        # Fallback cho các node không tìm thấy
        for nid in node_ids:
            if nid not in node_map:
                node_map[nid] = f"Node_{nid}"
        
        return node_map


# =============================
# RETRIEVAL FUNCTION
# =============================
def query_subgraph(question, k=10, threshold=0.3, rerank_top_k=5):
    """
    Query subgraph with Cohere reranking
    
    Args:
        question: User query
        k: Number of candidates to retrieve from Milvus
        threshold: Minimum similarity threshold for Milvus
        rerank_top_k: Number of top results after reranking (default: 5)
    """
    # 🔥 Encode query theo chuẩn E5
    q = encode_e5([f"query: {question}"])[0].tolist()

    # ✅ Milvus search - chỉ lấy node_id (không cần output_fields)
    res = col.search(
        data=[q],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 128}},
        limit=k,
        output_fields=[]  # ✅ Không lấy field nào vì chỉ có node_id và embedding
    )

    hits = res[0]

    print("\n====== Milvus Search Debug ======")
    anchor_candidates = []
    node_ids_to_fetch = []

    for idx, h in enumerate(hits, 1):
        score = h.distance
        node_id = h.id  # ✅ Lấy trực tiếp từ h.id (primary key)
        
        print(f"  #{idx:02d} | node_id={node_id} | score={score:.4f}"
            f"{'  ✔️ keep' if score >= threshold else '  ❌ discard'}")

        if score >= threshold:
            anchor_candidates.append({
                "node_id": node_id,
                "score": score
            })
            node_ids_to_fetch.append(node_id)

    print("=================================\n")

    if not anchor_candidates:
        return [], []

    # ✅ Lấy node names từ Neo4j
    print(f"🔍 Fetching {len(node_ids_to_fetch)} node names from Neo4j...")
    node_name_map = get_node_names_from_neo4j(node_ids_to_fetch)
    
    # ✅ Thêm name vào anchor_candidates
    for item in anchor_candidates:
        item["name"] = node_name_map.get(item["node_id"], f"Node_{item['node_id']}")

    # ✅ RERANK với Cohere class
    print(f"\n====== Cohere Rerank (Top {rerank_top_k}) ======")
    reranked = reranker.rerank_anchors(question, anchor_candidates, top_k=rerank_top_k)
    
    for idx, item in enumerate(reranked, 1):
        print(f"  #{idx} | node_id={item['node_id']} | "
              f"cohere_score={item['cohere_score']:.4f} | "
              f"milvus_score={item['original_milvus_score']:.4f} | "
              f"name={item['name']}")
    print("=================================\n")

    # Extract final anchor IDs
    anchor_ids = [item["node_id"] for item in reranked]

    # Expand Neo4j subgraph
    CY = """
    MATCH (a:Entity) WHERE a.id IN $ids
    CALL apoc.path.expandConfig(a, {
        relationshipFilter:"TARGETS>|ALLEVIATES>|WORSENED_BY>|TRIGGERED_BY>|HAS_FREQUENCY>|HAS_DURATION>|HAS_SEVERITY>|OCCURRED_AT>|NEGATES>|RELATED_TO>|TARGETS<|ALLEVIATES<|WORSENED_BY<|TRIGGERED_BY<|HAS_FREQUENCY<|HAS_DURATION<|HAS_SEVERITY<|OCCURRED_AT<|NEGATES<|RELATED_TO<",
        maxLevel:2, bfs:true, limit:20, uniqueness:"NODE_GLOBAL"
    }) YIELD path

    WITH collect(DISTINCT a) AS anchors, collect(path) AS paths

    WITH 
        apoc.coll.toSet(anchors) +
        apoc.coll.toSet([n IN apoc.coll.flatten([p IN paths | nodes(p)]) | n]) AS nodes,
        apoc.coll.toSet([r IN apoc.coll.flatten([p IN paths | relationships(p)]) | r]) AS rels

    RETURN nodes, rels
    """

    with driver.session() as s:
        rec = s.run(CY, {"ids": anchor_ids}).single()
        nodes = rec["nodes"]
        rels  = rec["rels"]
        return nodes, rels


def build_triples(nodes, rels) -> List[Dict[str, str]]:
    node_map = {}
    for n in nodes:
        label = list(n.labels)[0] if n.labels else "Node"
        name = n.get("name", n.get("label", str(n.id)))
        node_map[n.id] = {"id": n.id, "label": label, "name": name}

    triples = []
    for r in rels:
        s_id = r.start_node.id
        o_id = r.end_node.id
        p = r.type
        s_name = node_map.get(s_id, {"name": str(s_id)})["name"]
        o_name = node_map.get(o_id, {"name": str(o_id)})["name"]
        triples.append({"subject": s_name, "predicate": p, "object": o_name})
    return triples


def export_to_json(nodes, rels):
    node_map = {}
    all_nodes = []
    all_edges = []
    triples = []

    for n in nodes:
        node_data = {
            "id": n.id,
            "labels": list(n.labels),
        }
        for key in n.keys():
            node_data[key] = n.get(key)

        node_map[n.id] = node_data
        all_nodes.append(node_data)

    for r in rels:
        s = r.start_node.id
        o = r.end_node.id
        p = r.type

        edge_data = {
            "source": s,
            "predicate": p,
            "target": o
        }
        all_edges.append(edge_data)

        triples.append({
            "subject": node_map[s].get("name", str(s)),
            "predicate": p,
            "object": node_map[o].get("name", str(o)),
        })

    with open("nodes.json", "w", encoding="utf-8") as f:
        json.dump(all_nodes, f, indent=2, ensure_ascii=False)

    with open("edges.json", "w", encoding="utf-8") as f:
        json.dump(all_edges, f, indent=2, ensure_ascii=False)

    with open("triples.json", "w", encoding="utf-8") as f:
        json.dump(triples, f, indent=2, ensure_ascii=False)

    print("\n✅ Export xong!")

    return all_nodes, all_edges, triples


if __name__ == "__main__":
    # Path to API key file (relative to project root)
    keys_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Input", "api_key_respone.txt")
    translator = GeminiTranslator(keys_file=keys_file)
    
    q = "Tôi bị đau lưng nhiều, có thể giúp tôi khắc phục vấn đề này không?"
    question = translator.translate_question(q)
    print(f"\n=== USER QUESTION ===\n{question}\n")
    
    K = 10
    THRESHOLD = 0.8
    RERANK_TOP_K = 3
    
    nodes, rels = query_subgraph(question, k=K, threshold=THRESHOLD, rerank_top_k=RERANK_TOP_K)
    
    if not nodes:
        print("\n" + "="*60)
        print("❌ NO RELEVANT KNOWLEDGE FOUND")
        print("="*60)
        exit(0)
    
    print(f"✅ Found {len(nodes)} nodes, {len(rels)} edges")

    triples = build_triples(nodes, rels)
    print("\n=== TRIPLES JSON ===")
    print(json.dumps(triples[:10], indent=2, ensure_ascii=False))
    if len(triples) > 10:
        print(f"... (và {len(triples)-10} triples khác)")

    if GOOGLE_API_KEY and GOOGLE_API_KEY != "YOUR_API_KEY":
        print("\n=== GEMINI ANSWER ===")
        a = answer_with_gemini(triples, question)
        print("\n📝 Raw answer (EN):\n", a)
        
        answer = translator.translate_answer(a)
        print("\n✅ Translated answer (VI):\n", answer)

    export_to_json(nodes, rels)