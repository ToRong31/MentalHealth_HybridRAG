from .workflow import build_kg_graph
from .state import KGState


def run_example():
    graph = build_kg_graph()

    question = "I'm struggling with grief and sadness. What can help me cope?"

    initial_state: KGState = {
        "question": question,
        "query_embedding": [],
        "anchors": [],
        "nodes": [],
        "rels": [],
        "graph_context": "",
        "answer": "",
        "done": False,
    }

    final_state = graph.invoke(initial_state)

    print("\n=== SUBGRAPH CONTEXT ===")
    print(final_state["graph_context"])

    print("\n=== THERAPIST ANSWER ===")
    print(final_state["answer"])


if __name__ == "__main__":
    run_example()
