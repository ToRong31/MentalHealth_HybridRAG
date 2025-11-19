from langgraph.graph import StateGraph, END

from .state import KGState
from .graph_nodes import (
    encode_node,
    milvus_rerank_node,
    neo4j_subgraph_node,
    build_subgraph_context_node,
    answer_node,
)


def build_kg_graph():
    builder = StateGraph(KGState)

    builder.add_node("encode", encode_node)
    builder.add_node("milvus_rerank", milvus_rerank_node)
    builder.add_node("neo4j_subgraph", neo4j_subgraph_node)
    builder.add_node("build_subgraph_context", build_subgraph_context_node)
    builder.add_node("answer", answer_node)

    builder.set_entry_point("encode")

    builder.add_edge("encode", "milvus_rerank")
    builder.add_edge("milvus_rerank", "neo4j_subgraph")
    builder.add_edge("neo4j_subgraph", "build_subgraph_context")
    builder.add_edge("build_subgraph_context", "answer")
    builder.add_edge("answer", END)

    return builder.compile()
