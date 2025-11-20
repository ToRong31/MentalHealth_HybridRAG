"""
Interactive Ingestion Runner
Simple script to run knowledge graph ingestion pipeline
Place this in: src/ingestion/graph/run.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.ingestion.graph import (
    Config,
    create_pipeline,
    load_api_keys_from_file
)
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'ingestion.log')
    ]
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*70)
    print("🧠 KNOWLEDGE GRAPH INGESTION PIPELINE")
    print("="*70 + "\n")


def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    data_raw = project_root / "data" / "raw"
    input_json = data_raw / "input.json"
    api_keys = project_root / "src" / "api_key_manager" / "build_graph" / "api_key.txt"
    
    issues = []
    
    if not data_raw.exists():
        issues.append("❌ data/raw/ directory not found")
    
    if not input_json.exists():
        issues.append("❌ data/raw/input.json not found")
    else:
        print(f"   ✅ Found input file: {input_json}")
    
    if not api_keys.exists():
        issues.append("❌ src/api_key_manager/build_graph/api_key.txt not found")
    else:
        # Count keys
        with open(api_keys, 'r') as f:
            key_count = len([line for line in f if line.strip()])
        print(f"   ✅ Found {key_count} API keys")
    
    if issues:
        print("\n⚠️  Missing requirements:")
        for issue in issues:
            print(f"   {issue}")
        print("\nPlease fix these issues before running.\n")
        return False
    
    print("   ✅ All requirements met!\n")
    return True


def get_user_choice():
    """Get user's choice for what to run"""
    print("What would you like to do?\n")
    print("  1. 🚀 Run FULL pipeline (Extract → Neo4j → Milvus)")
    print("  2. 🔍 Extract only (LLM extraction to CSV)")
    print("  3. 🗄️  Neo4j import only (CSV → Neo4j)")
    print("  4. 🧮 Milvus embedding only (CSV → Milvus)")
    print("  5. 📊 Check pipeline status")
    print("  6. ❌ Exit")
    print()
    
    while True:
        choice = input("Enter your choice (1-6): ").strip()
        if choice in ['1', '2', '3', '4', '5', '6']:
            return choice
        print("❌ Invalid choice. Please enter 1-6.")


def get_config_options():
    """Get simple configuration from user"""
    print("\n" + "-"*70)
    print("⚙️  CONFIGURATION")
    print("-"*70 + "\n")
    
    # Quick or custom
    mode = input("Use default settings? (Y/n): ").strip().lower()
    
    if mode == 'n':
        # Custom config
        batch_size = input("  Batch size (default: 5): ").strip()
        batch_size = int(batch_size) if batch_size else 5
        
        print("\n  Available models:")
        print("    1. gemini-2.5-flash (fast, default)")
        print("    2. gemini-2.5-flash-lite")
        model_choice = input("  Select model (1-2): ").strip()
        model_name = 'gemini-2.5-flash-lite' if model_choice == '2' else 'gemini-2.5-flash'
        
        index_filter = input("\n  Process specific items (e.g., '1-100', leave empty for all): ").strip()
        index_filter = index_filter if index_filter else None
        
        clear_neo4j = input("  Clear existing Neo4j data? (y/N): ").strip().lower() == 'y'
        recreate_milvus = input("  Recreate Milvus collection? (y/N): ").strip().lower() == 'y'
    else:
        # Default config
        batch_size = 5
        model_name = 'gemini-2.5-flash-lite'
        index_filter = None
        clear_neo4j = False
        recreate_milvus = False
        print("  ✅ Using default settings")
    
    print()
    return {
        'batch_size': batch_size,
        'model_name': model_name,
        'index_filter': index_filter,
        'clear_neo4j': clear_neo4j,
        'recreate_milvus': recreate_milvus
    }


def check_status():
    """Check pipeline status"""
    print("\n" + "="*70)
    print("📊 PIPELINE STATUS")
    print("="*70 + "\n")
    
    data_processed = project_root / "data" / "processed"
    
    # Check CSV files
    nodes_csv = data_processed / "nodes.csv"
    edges_csv = data_processed / "edges.csv"
    processed_txt = data_processed / "processed_id.txt"
    errors_txt = data_processed / "errors_id.txt"
    
    if nodes_csv.exists():
        with open(nodes_csv, 'r') as f:
            node_count = sum(1 for _ in f) - 1  # Subtract header
        print(f"  ✅ Nodes extracted: {node_count}")
    else:
        print("  ⚠️  No nodes.csv found")
    
    if edges_csv.exists():
        with open(edges_csv, 'r') as f:
            edge_count = sum(1 for _ in f) - 1
        print(f"  ✅ Edges extracted: {edge_count}")
    else:
        print("  ⚠️  No edges.csv found")
    
    if processed_txt.exists():
        with open(processed_txt, 'r') as f:
            processed_count = len([line for line in f if line.strip()])
        print(f"  ✅ Processed items: {processed_count}")
    else:
        print("  ⚠️  No processed_id.txt found")
    
    if errors_txt.exists():
        with open(errors_txt, 'r') as f:
            error_count = len([line for line in f if line.strip()])
        if error_count > 0:
            print(f"  ⚠️  Failed items: {error_count}")
        else:
            print(f"  ✅ No errors")
    
    print("\n" + "="*70 + "\n")
    input("Press Enter to continue...")


def run_full_pipeline(pipeline, options):
    """Run full pipeline"""
    print("\n" + "="*70)
    print("🚀 STARTING FULL PIPELINE")
    print("="*70)
    print(f"  • Batch size: {options['batch_size']}")
    print(f"  • Model: {options['model_name']}")
    print(f"  • Index filter: {options['index_filter'] or 'All'}")
    print(f"  • Clear Neo4j: {options['clear_neo4j']}")
    print(f"  • Recreate Milvus: {options['recreate_milvus']}")
    print("="*70 + "\n")
    
    input("Press Enter to start (or Ctrl+C to cancel)...")
    
    success = pipeline.run_full_pipeline(
        index_filter=options['index_filter'],
        clear_neo4j=options['clear_neo4j'],
        recreate_milvus=options['recreate_milvus']
    )
    
    return success


def run_extract_only(pipeline, options):
    """Run extraction only"""
    print("\n" + "="*70)
    print("🔍 STARTING EXTRACTION")
    print("="*70)
    print(f"  • Batch size: {options['batch_size']}")
    print(f"  • Model: {options['model_name']}")
    print(f"  • Index filter: {options['index_filter'] or 'All'}")
    print("="*70 + "\n")
    
    input("Press Enter to start (or Ctrl+C to cancel)...")
    
    pipeline.extractor.load_processed_and_errors()
    input_data = pipeline.load_input_data(options['index_filter'])
    
    print(f"\n📥 Loaded {len(input_data)} items to process\n")
    
    success = pipeline.run_extraction(input_data)
    
    return success


def run_neo4j_only(pipeline, options):
    """Run Neo4j import only"""
    print("\n" + "="*70)
    print("🗄️  STARTING NEO4J IMPORT")
    print("="*70)
    print(f"  • Clear existing: {options['clear_neo4j']}")
    print("="*70 + "\n")
    
    if options['clear_neo4j']:
        confirm = input("⚠️  This will DELETE all existing data in Neo4j. Continue? (yes/N): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return False
    
    success = pipeline.run_neo4j_import(clear_existing=options['clear_neo4j'])
    return success


def run_milvus_only(pipeline, options):
    """Run Milvus embedding only"""
    print("\n" + "="*70)
    print("🧮 STARTING MILVUS EMBEDDING")
    print("="*70)
    print(f"  • Recreate collection: {options['recreate_milvus']}")
    print("="*70 + "\n")
    
    if options['recreate_milvus']:
        confirm = input("⚠️  This will DELETE existing embeddings. Continue? (yes/N): ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return False
    
    success = pipeline.run_embedding(recreate_collection=options['recreate_milvus'])
    return success


def main():
    """Main function"""
    try:
        print_banner()
        
        # Check requirements
        if not check_requirements():
            return 1
        
        # Get user choice
        choice = get_user_choice()
        
        if choice == '6':
            print("\n👋 Goodbye!\n")
            return 0
        
        if choice == '5':
            check_status()
            return main()  # Return to menu
        
        # Get configuration
        options = get_config_options()
        
        print("\n📦 Initializing pipeline...")
        
        # Load API keys
        api_key_file = project_root / "src" / "api_key_manager" / "build_graph" / "api_key.txt"
        api_keys = load_api_keys_from_file(str(api_key_file))
        print(f"   ✅ Loaded {len(api_keys)} API keys")
        
        # Create config
        config = Config(
            batch_size=options['batch_size'],
            model_name=options['model_name']
        )
        print(f"   ✅ Config: {options['model_name']}, batch={options['batch_size']}")
        
        # Create pipeline
        pipeline = create_pipeline(api_keys=api_keys, config=config)
        print("   ✅ Pipeline initialized\n")
        
        # Run selected operation
        if choice == '1':
            success = run_full_pipeline(pipeline, options)
        elif choice == '2':
            success = run_extract_only(pipeline, options)
        elif choice == '3':
            success = run_neo4j_only(pipeline, options)
        elif choice == '4':
            success = run_milvus_only(pipeline, options)
        
        # Print result
        print("\n" + "="*70)
        if success:
            print("✅ OPERATION COMPLETED SUCCESSFULLY")
        else:
            print("❌ OPERATION FAILED - Check logs for details")
        print("="*70 + "\n")
        
        # Cleanup
        pipeline.close()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user\n")
        return 1
    except Exception as e:
        print(f"\n\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()
        logger.error("Fatal error", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())