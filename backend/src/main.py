from .workflow import build_kg_graph, KGState



def run_example():
    graph = build_kg_graph()

    # Test với câu hỏi về mental health
    question = "I'm feeling very anxious and stressed out. What can I do to help myself?"
    
    # Test với câu hỏi high-risk (uncomment để test)
    # question = "Tôi không muốn sống nữa, tôi muốn tự tử"
    
    # Test với câu hỏi không liên quan mental health (uncomment để test)
    # question = "What is the weather today?"

    initial_state: KGState = {
        "question": question,
        "is_mental_health_related": False,  # Sẽ được set bởi safety_check_node
        "is_high_risk": False,  # Sẽ được set bởi safety_check_node
        "query_embedding": [],
        "anchors": [],
        "nodes": [],
        "rels": [],
        "graph_context": "",
        "answer": "",
        "done": False,
    }

    final_state = graph.invoke(initial_state)

    print("\n=== SAFETY CHECK RESULTS ===")
    print(f"Is Mental Health Related: {final_state.get('is_mental_health_related')}")
    print(f"Is High Risk: {final_state.get('is_high_risk')}")

    if final_state.get("graph_context"):
        print("\n=== SUBGRAPH CONTEXT ===")
        print(final_state["graph_context"])

    print("\n=== THERAPIST ANSWER ===")
    print(final_state["answer"])


if __name__ == "__main__":
    run_example()
