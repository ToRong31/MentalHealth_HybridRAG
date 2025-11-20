from typing import TypedDict, List, Dict, Any


class KGState(TypedDict):
    question: str
    is_mental_health_related: bool  
    is_high_risk: bool  
    query_embedding: List[float]
    anchors: List[Dict[str, Any]]
    nodes: List[Any]
    rels: List[Any]
    graph_context: str
    answer: str
    done: bool
