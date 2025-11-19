from __future__ import annotations
from typing import List, Literal, TypedDict, Any, Dict, Optional

from langgraph.graph import StateGraph, START, END

# =========================
# 1. ĐỊNH NGHĨA STATE
# =========================

class MHState(TypedDict, total=False):
    # Input chính
    question: str

    # Phân loại intent / an toàn
    intent: str              # "info" | "self_help" | "crisis" | ...
    safety_flag: bool        # True nếu nguy cơ cao

    # Thông tin khái niệm (concept) từ query
    concepts: List[Dict[str, Any]]   # ví dụ: [{"type": "SYMPTOM", "name": "anxiety"}, ...]

    # Kết quả retrieval
    graph_triples_text: str          # facts từ subgraph (triples dạng text)
    vector_context: str              # context từ vector store (answers bác sĩ, tài liệu...)

    # Context đã merge
    combined_context: str

    # Output
    draft_answer: str
    answer: str


# =========================
# 2. PLACEHOLDER CHO LLM / VECTOR / GRAPH
# =========================

# TODO: thay bằng client/model bạn dùng (OpenAI, Groq, v.v.)
class DummyLLM:
    def invoke(self, prompt: str) -> str:
        # Chỉ demo, bạn thay bằng call thật
        return "DUMMY_ANSWER (hãy thay DummyLLM bằng LLM thật)."

llm_classify = DummyLLM()
llm_answer   = DummyLLM()
llm_review   = DummyLLM()

# TODO: thay bằng vector store thật (Chroma, FAISS…)
class DummyVectorStore:
    def similarity_search(self, query: str, k: int = 5):
        # Trả về list docs giả
        return [
            type("Doc", (), {"page_content": f"Đoạn context giả #{i+1} cho: {query}"})
            for i in range(k)
        ]

vector_store = DummyVectorStore()

# TODO: thay bằng graph thật, ví dụ networkx.MultiDiGraph với node kiểu:
#   ("SYMPTOM", "anxiety")
#   ("COPING_STRATEGY", "self-care")
#   ...
import networkx as nx
G = nx.MultiDiGraph()
# Bạn sẽ phải build G từ CSV node/edge của bạn


# =========================
# 3. NODE: SAFETY CHECK
# =========================

def node_safety_check(state: MHState) -> MHState:
    q = state["question"]

    # TODO: dùng LLM thật để phân loại
    prompt = f"""
Bạn là bộ lọc an toàn cho trợ lý sức khỏe tâm thần.

Câu người dùng:
\"\"\"{q}\"\"\"

1. intent: "info" (hỏi thông tin), "self_help" (tìm cách tự vượt qua),
   "crisis" (có ý định tự hại, tự sát, gây hại).

2. safety_flag: true nếu có dấu hiệu "crisis", false nếu không.

Hãy trả lời JSON:
{{
  "intent": "...",
  "safety_flag": true/false
}}
"""
    raw = llm_classify.invoke(prompt)
    # TODO: parse JSON thật (dùng json.loads). Ở skeleton mình giả lập:
    intent = "info"
    safety_flag = False

    return {
        "intent": intent,
        "safety_flag": safety_flag,
    }


# =========================
# 4. NODE: CRISIS RESPONSE
# =========================

def node_crisis_response(state: MHState) -> MHState:
    msg = (
        "Mình rất tiếc khi nghe bạn đang trải qua giai đoạn khó khăn.\n\n"
        "Mình chỉ có thể cung cấp thông tin chung, không thay thế được bác sĩ "
        "hay các dịch vụ hỗ trợ khẩn cấp. Nếu bạn đang có ý nghĩ làm hại bản thân "
        "hoặc người khác, hãy tìm trợ giúp NGAY LẬP TỨC:\n\n"
        "- Liên hệ các đường dây nóng hỗ trợ khủng hoảng tinh thần tại nơi bạn sống\n"
        "- Nói chuyện với người thân đáng tin cậy\n"
        "- Đến bệnh viện hoặc cơ sở y tế gần nhất\n"
    )
    return {"answer": msg}


# =========================
# 5. NODE: DETECT CONCEPTS (SYMPTOM / STRATEGY / INTERVENTION…)
# =========================

def node_detect_concepts(state: MHState) -> MHState:
    q = state["question"]

    # TODO: dùng LLM / embedding để detect concept (SYMPTOM, COPING_STRATEGY...)
    # Ở đây skeleton trả về giả lập cho dễ hình dung:
    concepts = [
        {"type": "SYMPTOM", "name": "anxiety"},
        {"type": "SYMPTOM", "name": "tension"},
    ]

    return {"concepts": concepts}


# =========================
# 6. NODE: GRAPH RETRIEVER (LẤY SUBGRAPH + TRIPLES)
# =========================

from collections import deque

def extract_subgraph(G: nx.MultiDiGraph,
                     seeds: List[tuple],
                     max_depth: int = 2,
                     max_nodes: int = 40) -> nx.MultiDiGraph:
    if not seeds:
        return G.subgraph([]).copy()

    visited = set(seeds)
    q = deque([(n, 0) for n in seeds])
    nodes = set(seeds)

    while q and len(nodes) < max_nodes:
        node, depth = q.popleft()
        if depth >= max_depth:
            continue

        for neighbor in G.neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                nodes.add(neighbor)
                q.append((neighbor, depth + 1))

    return G.subgraph(nodes).copy()


def subgraph_to_triples(H: nx.MultiDiGraph) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []

    for u, v, data in H.edges(data=True):
        rel = data.get("rel")
        su_type, su_name = u
        ob_type, ob_name = v

        # Lọc loại quan hệ mình quan tâm cho mental health
        if rel in ["HELPED_BY", "TREATED_BY", "RELATED_TO"]:
            triples.append({
                "subject": {"type": su_type, "name": su_name},
                "relation": rel,
                "object": {"type": ob_type, "name": ob_name},
            })
    return triples


def triples_to_text(triples: List[Dict[str, Any]]) -> str:
    lines = []
    for t in triples:
        s_type = t["subject"]["type"]
        s_name = t["subject"]["name"]
        rel    = t["relation"]
        o_type = t["object"]["type"]
        o_name = t["object"]["name"]
        lines.append(f"- ({s_type}: {s_name}) -[{rel}]-> ({o_type}: {o_name})")
    return "\n".join(lines)


def node_graph_retriever(state: MHState) -> MHState:
    concepts = state.get("concepts", [])

    # Chuyển concept -> seed nodes (phụ thuộc cách bạn đặt node trong G)
    seed_nodes = [(c["type"], c["name"]) for c in concepts if (c["type"], c["name"]) in G.nodes]

    H = extract_subgraph(G, seed_nodes, max_depth=2, max_nodes=40)
    triples = subgraph_to_triples(H)
    triples_text = triples_to_text(triples)

    return {"graph_triples_text": triples_text}


# =========================
# 7. NODE: VECTOR RETRIEVER (DÙNG ANSWER BÁC SĨ)
# =========================

def node_vector_retriever(state: MHState) -> MHState:
    q = state["question"]
    docs = vector_store.similarity_search(q, k=5)

    # Gộp nội dung lại thành 1 string để dễ nhét vào LLM
    context = "\n\n".join(
        f"- Đoạn {i+1}: {doc.page_content}"
        for i, doc in enumerate(docs)
    )
    return {"vector_context": context}


# =========================
# 8. NODE: MERGE CONTEXT
# =========================

def node_merge_context(state: MHState) -> MHState:
    graph_facts = state.get("graph_triples_text", "")
    vec_ctx     = state.get("vector_context", "")

    parts = []
    if graph_facts:
        parts.append("FACTS từ knowledge graph:\n" + graph_facts)
    if vec_ctx:
        parts.append("Các đoạn trả lời / tài liệu liên quan:\n" + vec_ctx)

    combined = "\n\n".join(parts)
    return {"combined_context": combined}


# =========================
# 9. NODE: ANSWER LLM (DRAFT)
# =========================

def node_answer_llm(state: MHState) -> MHState:
    q = state["question"]
    ctx = state.get("combined_context", "")

    prompt = f"""
Bạn là trợ lý cung cấp thông tin về sức khỏe tâm thần.

Nguyên tắc:
- Chỉ cung cấp thông tin mang tính giáo dục, giải thích chung.
- KHÔNG chẩn đoán người dùng mắc bệnh gì.
- KHÔNG đề xuất thuốc hoặc thay thế bác sĩ.
- Luôn khuyến khích người dùng tìm sự giúp đỡ chuyên môn nếu triệu chứng kéo dài hoặc nặng.

Dưới đây là các thông tin liên quan (facts + đoạn trả lời mẫu từ bác sĩ):

---------------- CONTEXT BẮT ĐẦU ----------------
{ctx}
---------------- CONTEXT KẾT THÚC ----------------

CÂU HỎI CỦA NGƯỜI DÙNG:
\"\"\"{q}\"\"\"

Hãy:
1. Tóm tắt lại bạn hiểu vấn đề của người dùng là gì (ở mức tổng quát, KHÔNG chẩn đoán).
2. Giải thích một số điểm chính dựa trên context.
3. Gợi ý vài bước tự chăm sóc an toàn (ví dụ: điều chỉnh giấc ngủ, hoạt động nhẹ, kỹ thuật thư giãn, mindfulness đơn giản...).
4. Nhắc rằng đây không phải chẩn đoán, khuyến khích tìm gặp chuyên gia nếu cần.

Trả lời bằng tiếng Việt, giọng nhẹ nhàng, có cấu trúc rõ (1., 2., 3., ...).
"""
    text = llm_answer.invoke(prompt)
    return {"draft_answer": text}


# =========================
# 10. NODE: REVIEW & REFINE (SAFETY / CLARITY)
# =========================

def node_review_answer(state: MHState) -> MHState:
    draft = state.get("draft_answer", "")

    prompt = f"""
Bạn là reviewer an toàn cho nội dung về sức khỏe tâm thần.

Đây là bản nháp câu trả lời:

\"\"\"{draft}\"\"\"

Hãy kiểm tra:
- Có chỗ nào giống như đang chẩn đoán trực tiếp (ghi rõ bệnh, rối loạn) cho người dùng không?
- Có nhắc tới thuốc, liều, dược chất cụ thể không?
- Có gợi ý hành vi nguy hiểm (tự hại, bỏ thuốc, dừng điều trị, v.v.) không?

Nếu có nội dung không phù hợp, hãy sửa lại thành một câu trả lời:
- Mang tính thông tin chung, không chẩn đoán, không kê thuốc.
- Nhấn mạnh khuyến khích tìm sự trợ giúp chuyên môn khi cần.
- Giữ giọng nói nhẹ nhàng, hỗ trợ.

Nếu bản nháp đã ổn, chỉ cần chỉnh sửa nhẹ cho rõ ràng và ấm áp hơn.

Xuất ra trực tiếp câu trả lời cuối cùng bằng tiếng Việt.
"""
    final_text = llm_review.invoke(prompt)
    return {"answer": final_text}


# =========================
# 11. ROUTING FUNCTIONS
# =========================

def route_safety(state: MHState) -> Literal["crisis_response", "detect_concepts"]:
    if state.get("safety_flag"):
        return "crisis_response"
    return "detect_concepts"


# =========================
# 12. BUILD LANGGRAPH
# =========================

def build_graph() -> Any:
    builder = StateGraph(MHState)

    # Đăng ký node
    builder.add_node("safety_check", node_safety_check)
    builder.add_node("crisis_response", node_crisis_response)
    builder.add_node("detect_concepts", node_detect_concepts)
    builder.add_node("graph_retriever", node_graph_retriever)
    builder.add_node("vector_retriever", node_vector_retriever)
    builder.add_node("merge_context", node_merge_context)
    builder.add_node("answer_llm", node_answer_llm)
    builder.add_node("review_answer", node_review_answer)

    # Entry
    builder.add_edge(START, "safety_check")

    # Rẽ nhánh crisis / non-crisis
    builder.add_conditional_edges(
        "safety_check",
        route_safety,
        {
            "crisis_response": "crisis_response",
            "detect_concepts": "detect_concepts",
        },
    )

    # Crisis → END
    builder.add_edge("crisis_response", END)

    # Normal flow
    builder.add_edge("detect_concepts", "graph_retriever")
    builder.add_edge("detect_concepts", "vector_retriever")
    builder.add_edge(["graph_retriever", "vector_retriever"], "merge_context")
    builder.add_edge("merge_context", "answer_llm")
    builder.add_edge("answer_llm", "review_answer")
    builder.add_edge("review_answer", END)

    return builder.compile()


# =========================
# 13. VÍ DỤ GỌI GRAPH
# =========================

if __name__ == "__main__":
    app = build_graph()

    user_q = "Dạo này em rất lo lắng, khó ngủ, lúc nào cũng thấy căng thẳng."
    result: MHState = app.invoke({"question": user_q})

    print("=== ANSWER ===")
    print(result["answer"])
