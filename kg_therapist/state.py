from typing import TypedDict, List, Dict, Any


class KGState(TypedDict):
    question: str
    query_embedding: List[float]
    anchors: List[Dict[str, Any]]
    nodes: List[Any]
    rels: List[Any]
    graph_context: str
    answer: str
    done: bool
