"""RAG (Retrieval-Augmented Generation) components."""

# Lazy imports to avoid loading all dependencies when importing submodules
def __getattr__(name):
    if name == "run_graph":
        from .engine import run_graph
        return run_graph
    elif name == "build_kg_graph":
        from .workflow.workflow import build_kg_graph
        return build_kg_graph
    elif name == "KGState":
        from .workflow.workflow import KGState
        return KGState
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["run_graph", "build_kg_graph", "KGState"]

