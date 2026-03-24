"""
Script to test retrieval pipeline with scoring before/after rerank
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from typing import List, Dict, Any
import logging

# Try to import rich, fallback to basic print if not available
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Rich library not found. Install with: pip install rich")
    print("    Using basic output instead.\n")

from src.rag.retrieval.dense_retrieval import DenseRetrieval
from src.rag.vectors.embeddings import encode_e5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

if RICH_AVAILABLE:
    console = Console()


def test_retrieval_pipeline(
    query: str, 
    collection_name: str = "mental_health_diagnostic_support",
    milvus_top_k: int = 10, 
    rerank_top_k: int = 5
):
    """
    Test full retrieval pipeline using DenseRetrieval class
    """
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            f"[bold cyan]Query:[/bold cyan] {query}\n"
            f"[bold cyan]Collection:[/bold cyan] {collection_name}\n"
            f"[dim]Milvus Top-K: {milvus_top_k} | Rerank Top-K: {rerank_top_k}[/dim]",
            title="🔍 Dense Retrieval Test",
            border_style="cyan"
        ))
    else:
        print(f"\n{'='*80}")
        print(f"🔍 DENSE RETRIEVAL TEST")
        print(f"Query: {query}")
        print(f"Collection: {collection_name}")
        print(f"Milvus Top-K: {milvus_top_k} | Rerank Top-K: {rerank_top_k}")
        print(f"{'='*80}\n")
    
    # Initialize DenseRetrieval
    logger.info("Initializing DenseRetrieval...")
    dense_retrieval = DenseRetrieval(
        collection_name=collection_name,
        milvus_top_k=milvus_top_k
    )
    
    # Step 1: Get Milvus candidates (before rerank)
    logger.info("Step 1: Getting candidates from Milvus...")
    
    # Use DenseRetriever.retrieve() to get candidates with disease field
    milvus_results = dense_retrieval.dense_retriever.retrieve([query], top_k=milvus_top_k)
    # Results format: [[(node_id, score, disease), ...]]
    milvus_candidates = [
        {
            "node_id": node_id,
            "original_milvus_score": score,
            "disease": disease or "N/A"
        }
        for node_id, score, disease in milvus_results[0]
    ]
    
    logger.info(f"✅ Retrieved {len(milvus_candidates)} candidates from Milvus\n")
    
    # Show Milvus results
    if RICH_AVAILABLE:
        table1 = Table(title="Milvus Results (Before Rerank)", show_header=True, header_style="bold magenta")
        table1.add_column("Rank", style="dim", width=6)
        table1.add_column("Node ID", style="cyan", width=10)
        table1.add_column("Milvus Score", justify="right", width=15)
        table1.add_column("Disease", style="green", width=30)
        table1.add_column("Text Preview", style="white", width=60)
        
        for idx, cand in enumerate(milvus_candidates, 1):
            node_id = cand["node_id"]
            score = cand["original_milvus_score"]
            disease = cand["disease"]
            
            # Get text from DenseRetriever
            text = dense_retrieval.dense_retriever.get_dense_context_by_id(node_id)
            text_preview = (text[:80] + "...") if len(text) > 80 else text
            
            table1.add_row(
                str(idx),
                str(node_id),
                f"{score:.4f}",
                disease,
                text_preview
            )
        
        console.print(table1)
    else:
        print("\n📊 MILVUS RESULTS (Before Rerank)")
        print("-" * 140)
        print(f"{'Rank':<6} {'Node ID':<10} {'Score':<12} {'Disease':<30} {'Text Preview':<60}")
        print("-" * 140)
        
        for idx, cand in enumerate(milvus_candidates, 1):
            node_id = cand["node_id"]
            score = cand["original_milvus_score"]
            disease = cand["disease"]
            
            text = dense_retrieval.dense_retriever.get_dense_context_by_id(node_id)
            text_preview = (text[:50] + "...") if len(text) > 50 else text
            
            print(f"{idx:<6} {node_id:<10} {score:<12.4f} {disease[:29]:<30} {text_preview[:60]}")
        print()
    
    # Step 2: Full retrieval with reranking
    logger.info("Step 2: Running full DenseRetrieval.retrieve() with reranking...")
    
    result = dense_retrieval.retrieve(query=query, top_k=rerank_top_k)
    
    logger.info(f"✅ Retrieved and reranked to top {rerank_top_k} results\n")
    
    # Parse reranked results from metadata
    disease_details = result.metadata.get("disease_details", [])
    
    # Show reranked results
    if RICH_AVAILABLE:
        table2 = Table(title="Reranked Results (After Cohere Rerank)", show_header=True, header_style="bold green")
        table2.add_column("Rank", style="dim", width=6)
        table2.add_column("Node ID", style="cyan", width=10)
        table2.add_column("Milvus Score", justify="right", width=15)
        table2.add_column("Cohere Score", justify="right", width=15, style="bold green")
        table2.add_column("Score Δ", justify="right", width=12)
        table2.add_column("Disease", style="green", width=30)
        table2.add_column("Text Preview", style="white", width=60)
        
        for idx, detail in enumerate(disease_details, 1):
            chunk_id = detail["chunk_id"]
            cohere_score = detail["score"]
            disease = detail.get("disease", "N/A")
            
            # Find original Milvus score
            original_score = next(
                (c["original_milvus_score"] for c in milvus_candidates if c["node_id"] == chunk_id),
                0.0
            )
            score_delta = cohere_score - original_score
            
            # Get text
            text = dense_retrieval.dense_retriever.get_dense_context_by_id(chunk_id)
            text_preview = (text[:70] + "...") if len(text) > 70 else text
            
            # Color code score delta
            delta_color = "green" if score_delta > 0 else "red" if score_delta < 0 else "yellow"
            delta_str = f"[{delta_color}]{score_delta:+.4f}[/{delta_color}]"
            
            table2.add_row(
                str(idx),
                str(chunk_id),
                f"{original_score:.4f}",
                f"{cohere_score:.4f}",
                delta_str,
                disease,
                text_preview
            )
        
        console.print(table2)
    else:
        print("\n📊 RERANKED RESULTS (After Cohere)")
        print("-" * 150)
        print(f"{'Rank':<6} {'Node ID':<10} {'Milvus':<12} {'Cohere':<12} {'Delta':<12} {'Disease':<30} {'Text':<60}")
        print("-" * 150)
        
        for idx, detail in enumerate(disease_details, 1):
            chunk_id = detail["chunk_id"]
            cohere_score = detail["score"]
            disease = detail.get("disease", "N/A")
            
            original_score = next(
                (c["original_milvus_score"] for c in milvus_candidates if c["node_id"] == chunk_id),
                0.0
            )
            score_delta = cohere_score - original_score
            
            text = dense_retrieval.dense_retriever.get_dense_context_by_id(chunk_id)
            text_preview = (text[:50] + "...") if len(text) > 50 else text
            
            print(f"{idx:<6} {chunk_id:<10} {original_score:<12.4f} {cohere_score:<12.4f} {score_delta:+12.4f} {disease[:29]:<30} {text_preview[:60]}")
        print()
    
    # Step 3: Show final context and metadata
    logger.info("Step 3: Final Context and Metadata")
    
    if RICH_AVAILABLE:
        # Show diseases detected
        diseases = result.metadata.get("diseases", [])
        if diseases:
            console.print(f"\n[bold yellow]Diseases detected:[/bold yellow] {', '.join(diseases)}")
        
        # Show context preview
        context_preview = result.context[:500] + "..." if len(result.context) > 500 else result.context
        console.print(Panel(
            context_preview,
            title="📄 Final Context (Preview)",
            border_style="green"
        ))
        
        # Show metadata
        metadata_table = Table(show_header=False, box=None, padding=(0, 2))
        metadata_table.add_column("Field", style="bold cyan", width=20)
        metadata_table.add_column("Value", style="white", width=80)
        
        for key, value in result.metadata.items():
            if key not in ["disease_details"]:  # Skip disease_details (already shown)
                if isinstance(value, (list, dict)):
                    import json
                    value = json.dumps(value, indent=2)
                if isinstance(value, str) and len(value) > 200:
                    value = value[:200] + "..."
                metadata_table.add_row(key, str(value))
        
        console.print(Panel(metadata_table, title="Metadata", border_style="cyan"))
    else:
        diseases = result.metadata.get("diseases", [])
        if diseases:
            print(f"\n🏥 Diseases detected: {', '.join(diseases)}")
        
        context_preview = result.context[:300] + "..." if len(result.context) > 300 else result.context
        print(f"\n📄 FINAL CONTEXT (Preview)")
        print("-" * 100)
        print(context_preview)
        print("-" * 100)
        
        print(f"\n📊 METADATA")
        print("-" * 100)
        for key, value in result.metadata.items():
            if key not in ["disease_details"]:
                if isinstance(value, (list, dict)):
                    import json
                    value = json.dumps(value)
                if isinstance(value, str) and len(value) > 150:
                    value = value[:150] + "..."
                print(f"{key:20}: {value}")
        print()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test DenseRetrieval pipeline with Cohere reranking")
    parser.add_argument("--query", type=str, help="Query to test")
    parser.add_argument("--collection", type=str, default="mental_health_diagnostic_support", 
                       help="Milvus collection name")
    parser.add_argument("--milvus-top-k", type=int, default=10, 
                       help="Number of candidates from Milvus")
    parser.add_argument("--rerank-top-k", type=int, default=5, 
                       help="Number of results after rerank")
    
    args = parser.parse_args()
    
    try:
        query = args.query or "I've been feeling incredibly depressed for the past 4-5 months, with an intensity of 7-8 out of 10, sometimes much worse, triggered by work stress and a relationship breakup. This high stress level is causing physical symptoms like fatigue, exhaustion, stress-related headaches, and significant sleep difficulties including trouble falling asleep and frequent waking. I'm seeking someone to listen, a safe space to talk, and professional help."
        if not args.query:
            logger.info("No query provided, using default query")
        
        test_retrieval_pipeline(
            query=query,
            collection_name=args.collection,
            milvus_top_k=args.milvus_top_k,
            rerank_top_k=args.rerank_top_k
        )
        
        print("\n" + "="*100)
        print("✅ Test complete!")
        print("="*100)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()