"""
Milvus Embedder for Knowledge Graph Nodes
Creates embeddings for nodes using E5 model and stores them in Milvus
Uses shared embedding model and Milvus client from kg_therapist.vectors
"""
import os
import csv
import logging
from typing import List, Dict, Optional
from pathlib import Path

import numpy as np
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

from kg_therapist.config import (
    MILVUS_URI, 
    MILVUS_TOKEN, 
    MILVUS_DB, 
    MILVUS_COLLECTION,
    E5_MODEL_NAME
)
from kg_therapist.vectors.embeddings import encode_e5

from .models import Config

logger = logging.getLogger(__name__)


class MilvusEmbedder:
    """
    Creates embeddings for knowledge graph nodes using shared E5 model
    and stores them in Milvus vector database
    """
    
    def __init__(
        self,
        config: Config,
        nodes_file: str = "data/processed/nodes.csv",
        milvus_uri: Optional[str] = None,
        milvus_token: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_dim: int = 1024,
        batch_size: int = 32
    ):
        """
        Initialize Milvus embedder
        
        Args:
            config: Configuration object
            nodes_file: Path to nodes CSV file
            milvus_uri: Milvus connection URI (overrides config)
            milvus_token: Token for cloud Milvus (overrides config)
            collection_name: Name of Milvus collection (overrides config)
            embedding_dim: Dimension of embeddings (E5-large-v2: 1024)
            batch_size: Batch size for embedding generation
        """
        self.config = config
        self.nodes_file = Path(nodes_file)
        
        # Use provided values or fall back to config
        self.milvus_uri = milvus_uri or MILVUS_URI
        self.milvus_token = milvus_token or MILVUS_TOKEN
        self.collection_name = collection_name or MILVUS_COLLECTION
        self.milvus_db = MILVUS_DB
        self.embedding_dim = embedding_dim
        self.batch_size = batch_size
        
        logger.info(f"Using E5 model: {E5_MODEL_NAME}")
        logger.info(f"Embedding dimension: {self.embedding_dim}")
        
        # Initialize Milvus connection
        self._init_milvus_connection()
        
        logger.info(f"MilvusEmbedder initialized for collection: {self.collection_name}")
    
    def _init_milvus_connection(self):
        """Initialize connection to Milvus using shared config"""
        try:
            logger.info(f"Connecting to Milvus at {self.milvus_uri}")
            
            if self.milvus_token:
                # Cloud Milvus (Zilliz)
                connections.connect(
                    alias="default",
                    uri=self.milvus_uri,
                    token=self.milvus_token,
                    secure=True,
                    db_name=self.milvus_db
                )
            else:
                # Local Milvus
                host = self.milvus_uri.replace("http://", "").replace("https://", "").split(":")[0]
                port = self.milvus_uri.split(":")[-1] if ":" in self.milvus_uri else "19530"
                connections.connect(
                    alias="default",
                    host=host,
                    port=port
                )
            
            logger.info("✅ Connected to Milvus")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _encode_texts_batched(self, texts: List[str]) -> np.ndarray:
        """
        Encode texts to embeddings using shared E5 model in batches
        
        Args:
            texts: List of text strings
        
        Returns:
            NumPy array of embeddings [N, embedding_dim]
        """
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            # Use shared encode_e5 function
            embeddings = encode_e5(batch)
            all_embeddings.append(embeddings)
            
            if (i // self.batch_size + 1) % 10 == 0:
                logger.info(f"Encoded {i + len(batch)}/{len(texts)} texts")
        
        return np.vstack(all_embeddings)
    
    def load_nodes(self) -> List[Dict]:
        """
        Load nodes from CSV file
        
        Returns:
            List of node dictionaries
        """
        if not self.nodes_file.exists():
            logger.error(f"Nodes file not found: {self.nodes_file}")
            return []
        
        nodes = []
        with self.nodes_file.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                nodes.append(row)
        
        logger.info(f"Loaded {len(nodes)} nodes from {self.nodes_file}")
        return nodes
    
    def create_embeddings(self, nodes: List[Dict]) -> tuple[List[int], np.ndarray]:
        """
        Create embeddings for nodes using shared E5 model
        
        Args:
            nodes: List of node dictionaries with 'id', 'name', 'label'
        
        Returns:
            Tuple of (node_ids, embeddings)
        """
        if not nodes:
            return [], np.array([])
        
        logger.info(f"Creating embeddings for {len(nodes)} nodes...")
        
        # Prepare texts with E5 format: "passage: {name} [{label}]"
        node_ids = []
        texts = []
        
        for node in nodes:
            node_id = int(node['id'])
            name = (node.get('name') or '').strip()
            label = node.get('label', '').strip()
            
            # Create text representation
            if label:
                text = f"{name} [{label}]"
            else:
                text = name
            
            if not text:
                text = f"node {node_id}"
            
            # E5 requires "passage:" prefix for document encoding
            texts.append(f"passage: {text}")
            node_ids.append(node_id)
        
        # Generate embeddings using shared E5 model
        embeddings = self._encode_texts_batched(texts)
        
        logger.info(f"✅ Created {len(embeddings)} embeddings with shape {embeddings.shape}")
        
        return node_ids, embeddings
    
    def create_collection(self):
        """
        Create Milvus collection for storing node embeddings
        """
        # Check if collection already exists
        if self.collection_name in utility.list_collections():
            logger.info(f"Collection '{self.collection_name}' already exists")
            self.collection = Collection(self.collection_name)
            return
        
        logger.info(f"Creating collection: {self.collection_name}")
        
        try:
            # Define schema
            fields = [
                FieldSchema(
                    name="node_id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=False,
                    description="Node ID from knowledge graph"
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.embedding_dim,
                    description="E5 embedding vector"
                ),
            ]
            
            schema = CollectionSchema(
                fields,
                description=f"Knowledge Graph entities embeddings ({E5_MODEL_NAME})"
            )
            
            # Create collection
            self.collection = Collection(self.collection_name, schema)
            
            # Create HNSW index for fast similarity search
            index_params = {
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {
                    "M": 16,
                    "efConstruction": 200
                }
            }
            
            self.collection.create_index(
                field_name="embedding",
                index_params=index_params
            )
            
            logger.info(f"✅ Collection '{self.collection_name}' created with HNSW index")
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    def insert_embeddings(self, node_ids: List[int], embeddings: np.ndarray) -> bool:
        """
        Insert node embeddings into Milvus
        
        Args:
            node_ids: List of node IDs
            embeddings: NumPy array of embeddings
        
        Returns:
            True if successful
        """
        if len(node_ids) == 0:
            logger.warning("No embeddings to insert")
            return True
        
        try:
            logger.info(f"Inserting {len(node_ids)} embeddings into Milvus...")
            
            # Load collection
            self.collection.load()
            
            # Insert in batches
            insert_batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(node_ids), insert_batch_size):
                batch_ids = node_ids[i:i + insert_batch_size]
                batch_embeddings = embeddings[i:i + insert_batch_size]
                
                # Insert batch
                self.collection.insert([
                    batch_ids,
                    batch_embeddings.tolist()
                ])
                
                total_inserted += len(batch_ids)
                logger.info(f"Inserted {total_inserted}/{len(node_ids)} embeddings")
            
            # Flush to persist data
            self.collection.flush()
            
            logger.info(f"✅ Successfully inserted {total_inserted} embeddings")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert embeddings: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the Milvus collection
        
        Returns:
            Dictionary with collection stats
        """
        try:
            if self.collection_name not in utility.list_collections():
                return {"error": "Collection not found"}
            
            collection = Collection(self.collection_name)
            collection.load()
            
            stats = {
                "collection_name": self.collection_name,
                "num_entities": collection.num_entities,
                "embedding_dim": self.embedding_dim,
                "model": E5_MODEL_NAME
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    def run(self, recreate_collection: bool = False) -> bool:
        """
        Run the complete embedding pipeline
        
        Args:
            recreate_collection: Whether to drop and recreate collection
        
        Returns:
            True if successful
        """
        logger.info("\n" + "=" * 60)
        logger.info("STARTING MILVUS EMBEDDING")
        logger.info("=" * 60)
        
        try:
            # Drop collection if recreate requested
            if recreate_collection and self.collection_name in utility.list_collections():
                logger.warning(f"Dropping existing collection: {self.collection_name}")
                utility.drop_collection(self.collection_name)
            
            # Create collection
            self.create_collection()
            
            # Load nodes
            nodes = self.load_nodes()
            if not nodes:
                logger.error("No nodes to embed")
                return False
            
            # Create embeddings
            node_ids, embeddings = self.create_embeddings(nodes)
            
            if len(node_ids) == 0:
                logger.error("No embeddings created")
                return False
            
            # Insert into Milvus
            success = self.insert_embeddings(node_ids, embeddings)
            
            if not success:
                return False
            
            # Get and display stats
            stats = self.get_stats()
            logger.info("\n" + "=" * 60)
            logger.info("MILVUS EMBEDDING COMPLETED")
            logger.info("=" * 60)
            logger.info(f"Collection: {stats.get('collection_name', 'N/A')}")
            logger.info(f"Total Entities: {stats.get('num_entities', 0)}")
            logger.info(f"Embedding Dim: {stats.get('embedding_dim', 0)}")
            logger.info(f"Model: {stats.get('model', 'N/A')}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Milvus embedding failed: {e}", exc_info=True)
            return False
    
    def close(self):
        """Cleanup resources"""
        # Milvus connection is managed globally
        logger.info("Milvus embedder closed")
