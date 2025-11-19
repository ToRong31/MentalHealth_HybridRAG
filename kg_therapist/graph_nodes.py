import yaml
from typing import List, Dict, Any

from .state import KGState
from .embeddings import encode_e5
from .milvus_client import milvus_search
from .neo4j_client import get_node_names_from_neo4j, expand_subgraph
from .reranker import reranker
from .llm_gemini import llm
from .prompts import therapist_prompt


def build_subgraph_context(nodes, rels, anchors) -> str:
    node_map: Dict[int, Dict[str, Any]] = {}
    for n in nodes:
        labels = list(n.labels) if n.labels else []
        name = n.get("name") or n.get("label") or f"Node_{n.id}"
        node_map[n.id] = {
            "neo_id": n.id,
            "id": n.get("id"),
            "name": name,
            "labels": labels,
            "props": dict(n),
        }

    adjacency: Dict[int, List[Dict[str, Any]]] = {nid: [] for nid in node_map.keys()}
    for r in rels:
        s_id = r.start_node.id
        o_id = r.end_node.id
        rel_type = r.type
        rel_props = dict(r)

        adjacency[s_id].append({
            "direction": "out",
            "rel_type": rel_type,
            "target_id": o_id,
            "props": rel_props,
        })
        adjacency[o_id].append({
            "direction": "in",
            "rel_type": rel_type,
            "target_id": s_id,
            "props": rel_props,
        })

    anchor_business_ids = {a["node_id"] for a in anchors}
    anchor_internal_ids = []
    for neo_id, info in node_map.items():
        if info["id"] in anchor_business_ids:
            anchor_internal_ids.append(neo_id)

    def format_node_header(info, role: str) -> str:
        labels_str = ",".join(info["labels"]) if info["labels"] else "Entity"
        return f"[{role}] {info['name']} ({labels_str}, business_id={info['id']}, neo_id={info['neo_id']})"

    def format_rel_entry(src_info, rel, tgt_info) -> str:
        direction_symbol = "->" if rel["direction"] == "out" else "<-"
        rel_type = rel["rel_type"]
        props = rel["props"]
        source_id = props.get("source_id")
        labels_str = ",".join(tgt_info["labels"]) if tgt_info["labels"] else "Entity"
        base = (
            f"  - {rel_type} {direction_symbol} "
            f"{tgt_info['name']} ({labels_str}, business_id={tgt_info['id']})"
        )
        if source_id is not None:
            base += f" [source_id={source_id}]"
        return base

    lines: List[str] = []

    for neo_id in anchor_internal_ids:
        info = node_map[neo_id]
        lines.append(format_node_header(info, role="ANCHOR"))
        for rel in adjacency.get(neo_id, []):
            tgt_info = node_map.get(rel["target_id"])
            if tgt_info:
                lines.append(format_rel_entry(info, rel, tgt_info))
        lines.append("")

    other_ids = [nid for nid in node_map.keys() if nid not in anchor_internal_ids]
    if other_ids:
        lines.append("Other connected nodes:")
        for neo_id in other_ids:
            info = node_map[neo_id]
            lines.append(format_node_header(info, role="NEIGHBOR"))
            for rel in adjacency.get(neo_id, []):
                tgt_info = node_map.get(rel["target_id"])
                if tgt_info:
                    lines.append(format_rel_entry(info, rel, tgt_info))
            lines.append("")

    return "\n".join(lines).strip()


# --- LangGraph node functions ---

def encode_node(state: KGState) -> KGState:
    q = state["question"]
    emb = encode_e5([f"query: {q}"])[0]
    state["query_embedding"] = emb.tolist()
    return state


def milvus_rerank_node(state: KGState) -> KGState:
    question = state["question"]
    q_vec = state["query_embedding"]

    candidates = milvus_search(q_vec, limit=10, threshold=0.3)
    if not candidates:
        state["anchors"] = []
        return state

    node_ids = [c["node_id"] for c in candidates]
    name_map = get_node_names_from_neo4j(node_ids)
    for c in candidates:
        c["name"] = name_map.get(c["node_id"], f"Node_{c['node_id']}")

    reranked = reranker.rerank_anchors(question, candidates, top_k=5)
    state["anchors"] = reranked
    return state


def neo4j_subgraph_node(state: KGState) -> KGState:
    anchors = state["anchors"]
    if not anchors:
        state["nodes"], state["rels"] = [], []
        return state

    anchor_ids = [a["node_id"] for a in anchors]
    nodes, rels = expand_subgraph(anchor_ids)
    state["nodes"] = nodes
    state["rels"] = rels
    return state


def build_subgraph_context_node(state: KGState) -> KGState:
    state["graph_context"] = build_subgraph_context(
        state["nodes"],
        state["rels"],
        state["anchors"],
    )
    return state


def answer_node(state: KGState) -> KGState:
    q = state["question"]
    graph_context = state["graph_context"]





    prompt = therapist_prompt.replace("{{QUESTION}}", q).replace("{{GRAPH_CONTEXT}}", graph_context)
    answer = llm.invoke(prompt)

    state["answer"] = answer
    state["done"] = True
    return state
