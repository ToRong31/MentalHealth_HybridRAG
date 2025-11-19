"""
Knowledge Graph Ingestion Pipeline
Orchestrates the entire process: Extract → Embed → Write to Neo4j
"""
import os
import json
import time
import logging
from typing import List, Dict, Optional

from .models import Config
from .llm_extractor import GraphExtractor
from .api_key_manager import APIKeyManager, load_api_keys_from_file, load_api_keys_by_lines
from .milvus_embedder import MilvusEmbedder
from .neo4j_writer import Neo4jWriter

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    Main pipeline for ingesting data and building knowledge graph
    """
    
    def __init__(
        self,
        config: Config,
        api_key_manager: APIKeyManager,
        input_file: str = "data/raw/input.json",
        output_dir: str = "data/processed",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        milvus_uri: Optional[str] = None,
        milvus_token: Optional[str] = None
    ):
        """
        Initialize the ingestion pipeline
        
        Args:
            config: Configuration object
            api_key_manager: API key manager
            input_file: Path to input JSON file
            output_dir: Directory for output files
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            milvus_uri: Milvus connection URI
            milvus_token: Milvus token (for cloud/Zilliz)
        """
        self.config = config
        self.input_file = input_file
        self.output_dir = output_dir
        
        # Initialize components
        self.extractor = GraphExtractor(config, api_key_manager)
        self.api_manager = api_key_manager
        
        # Initialize Neo4j writer
        nodes_file = os.path.join(output_dir, "nodes.csv")
        edges_file = os.path.join(output_dir, "edges.csv")
        
        self.neo4j_writer = Neo4jWriter(
            config=config,
            nodes_file=nodes_file,
            edges_file=edges_file,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password
        )
        
        # Initialize Milvus embedder
        self.embedder = MilvusEmbedder(
            config=config,
            nodes_file=nodes_file,
            milvus_uri=milvus_uri,
            milvus_token=milvus_token
        )
        
        logger.info("Ingestion pipeline initialized")
    
    def load_input_data(self, index_filter: Optional[str] = None) -> List[Dict]:
        """
        Load input JSON data with optional filtering
        
        Args:
            index_filter: Filter string like "1-10" or "5,10,15"
        
        Returns:
            List of filtered input data
        """
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Loaded {len(data)} items from {self.input_file}")
        
        # Apply index filter if provided
        if index_filter:
            filtered_data = self._apply_index_filter(data, index_filter)
        else:
            filtered_data = data
        
        # Filter out already processed items
        final_data = []
        for item in filtered_data:
            item_id = str(item['id'])
            if item_id in self.extractor.error_ids:
                # Include error IDs for retry
                final_data.append(item)
            elif item_id not in self.extractor.processed_ids:
                # Include unprocessed IDs
                final_data.append(item)
        
        logger.info(f"Selected {len(final_data)} items to process")
        return final_data
    
    def _apply_index_filter(self, data: List[Dict], filter_str: str) -> List[Dict]:
        """
        Apply index filter to data
        
        Args:
            data: Full dataset
            filter_str: Filter like "1-10" or "5,10,15"
        
        Returns:
            Filtered data
        """
        indices = set()
        
        # Parse filter string
        parts = filter_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-10"
                start, end = part.split('-')
                indices.update(range(int(start), int(end) + 1))
            else:
                # Single index
                indices.add(int(part))
        
        # Filter by ID
        filtered = [item for item in data if int(item['id']) in indices]
        logger.info(f"Index filter '{filter_str}' selected {len(filtered)} items")
        return filtered
    
    def run_extraction(self, input_data: List[Dict]) -> bool:
        """
        Run the extraction phase
        
        Args:
            input_data: List of input items to process
        
        Returns:
            True if successful
        """
        if not input_data:
            logger.warning("No data to process")
            return False
        
        # Create batches
        batches = [
            input_data[i:i + self.config.batch_size]
            for i in range(0, len(input_data), self.config.batch_size)
        ]
        
        total_batches = len(batches)
        completed_batches = 0
        error_batches = 0
        
        logger.info("=" * 60)
        logger.info("Starting extraction phase")
        logger.info(f"Total items: {len(input_data)}")
        logger.info(f"Batch size: {self.config.batch_size}")
        logger.info(f"Total batches: {total_batches}")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Process each batch
        for i, batch in enumerate(batches, 1):
            success = self.extractor.extract_from_batch(batch, i, total_batches)
            
            if success:
                completed_batches += 1
            else:
                error_batches += 1
            
            # Progress update
            logger.info(
                f"Progress: {i}/{total_batches} batches | "
                f"✓ {completed_batches} completed | "
                f"✗ {error_batches} errors"
            )
            
            # Delay between batches
            if i < total_batches:
                logger.info(f"⏳ Waiting {self.config.batch_delay}s before next batch...")
                time.sleep(self.config.batch_delay)
        
        # Summary
        elapsed_time = time.time() - start_time
        stats = self.extractor.get_stats()
        
        logger.info("=" * 60)
        logger.info("Extraction phase completed")
        logger.info(f"Time elapsed: {elapsed_time:.1f} seconds")
        logger.info(f"Batches completed: {completed_batches}/{total_batches}")
        logger.info(f"Batches with errors: {error_batches}/{total_batches}")
        logger.info(f"Total nodes extracted: {stats['total_nodes']}")
        logger.info("=" * 60)
        
        self.api_manager.print_summary()
        
        return error_batches == 0
    
    def run_embedding(self, recreate_collection: bool = False) -> bool:
        """
        Run the embedding phase (create embeddings for nodes)
        
        Args:
            recreate_collection: Whether to drop and recreate Milvus collection
        
        Returns:
            True if successful
        """
        logger.info("=" * 60)
        logger.info("Starting embedding phase")
        logger.info("=" * 60)
        
        try:
            success = self.embedder.run(recreate_collection=recreate_collection)
            return success
        except Exception as e:
            logger.error(f"Embedding phase failed: {e}", exc_info=True)
            return False
    
    def run_neo4j_import(self, clear_existing: bool = False) -> bool:
        """
        Run the Neo4j import phase (write nodes and edges to Neo4j)
        
        Args:
            clear_existing: Whether to clear existing Neo4j data first
        
        Returns:
            True if successful
        """
        logger.info("=" * 60)
        logger.info("Starting Neo4j import phase")
        logger.info("=" * 60)
        
        try:
            success = self.neo4j_writer.run(clear_existing=clear_existing)
            return success
        except Exception as e:
            logger.error(f"Neo4j import phase failed: {e}", exc_info=True)
            return False
    
    def run_full_pipeline(
        self,
        index_filter: Optional[str] = None,
        clear_neo4j: bool = False,
        recreate_milvus: bool = False
    ) -> bool:
        """
        Run the complete pipeline: Extract → Import to Neo4j → Embed to Milvus
        
        Args:
            index_filter: Optional filter for input data
            clear_neo4j: Whether to clear existing Neo4j data
            recreate_milvus: Whether to recreate Milvus collection
        
        Returns:
            True if all phases completed successfully
        """
        logger.info("=" * 70)
        logger.info("STARTING FULL KNOWLEDGE GRAPH INGESTION PIPELINE")
        logger.info("=" * 70)
        
        try:
            # Phase 1: Load data
            logger.info("\n📥 PHASE 1: Loading input data")
            self.extractor.load_processed_and_errors()
            input_data = self.load_input_data(index_filter)
            
            if not input_data:
                logger.warning("No data to process. Pipeline complete.")
                return True
            
            # Phase 2: Extract graph
            logger.info("\n🔍 PHASE 2: Extracting knowledge graph with LLM")
            extraction_success = self.run_extraction(input_data)
            
            if not extraction_success:
                logger.warning("Extraction completed with some errors")
            
            # Phase 3: Import to Neo4j
            logger.info("\n📊 PHASE 3: Importing graph to Neo4j")
            import_success = self.run_neo4j_import(clear_existing=clear_neo4j)
            
            if not import_success:
                logger.error("Neo4j import failed, skipping embedding phase")
                return False
            
            # Phase 4: Create embeddings and store in Milvus
            logger.info("\n🧮 PHASE 4: Creating embeddings and storing in Milvus")
            embedding_success = self.run_embedding(recreate_collection=recreate_milvus)
            
            # Final summary
            logger.info("\n" + "=" * 70)
            logger.info("PIPELINE COMPLETED")
            logger.info(f"Extraction: {'✓ Success' if extraction_success else '⚠ With errors'}")
            logger.info(f"Neo4j Import: {'✓ Success' if import_success else '✗ Failed'}")
            logger.info(f"Milvus Embedding: {'✓ Success' if embedding_success else '✗ Failed'}")
            logger.info("=" * 70)
            
            return extraction_success and import_success and embedding_success
            
        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            return False
        finally:
            # Cleanup
            self.close()


    def close(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'neo4j_writer'):
                self.neo4j_writer.close()
            if hasattr(self, 'embedder'):
                self.embedder.close()
            logger.info("Pipeline resources cleaned up")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")


def create_pipeline(
    api_keys: List[str],
    config: Optional[Config] = None,
    input_file: str = "data/raw/input.json",
    output_dir: str = "data/processed",
    neo4j_uri: str = "bolt://localhost:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "password",
    milvus_uri: Optional[str] = None,
    milvus_token: Optional[str] = None
) -> IngestionPipeline:
    """
    Factory function to create ingestion pipeline
    
    Args:
        api_keys: List of API keys for LLM extraction
        config: Optional configuration (uses defaults if not provided)
        input_file: Path to input JSON file
        output_dir: Directory for output files
        neo4j_uri: Neo4j connection URI
        neo4j_user: Neo4j username
        neo4j_password: Neo4j password
        milvus_uri: Milvus connection URI (local or cloud)
        milvus_token: Milvus token for cloud (Zilliz)
    
    Returns:
        Configured IngestionPipeline instance
    """
    if config is None:
        config = Config()
    
    api_manager = APIKeyManager(api_keys, min_delay_between_calls=config.min_delay_between_calls)
    
    return IngestionPipeline(
        config=config,
        api_key_manager=api_manager,
        input_file=input_file,
        output_dir=output_dir,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        milvus_uri=milvus_uri,
        milvus_token=milvus_token
    )

