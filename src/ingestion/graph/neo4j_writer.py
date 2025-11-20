"""
Neo4j Writer for Knowledge Graph
Writes nodes and edges to Neo4j database
Uses shared Neo4j driver from src.graph
"""
import os
import csv
import logging
from typing import List, Dict, Optional
from pathlib import Path

from neo4j import GraphDatabase

from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

from .models import Config

logger = logging.getLogger(__name__)


class Neo4jWriter:
    """
    Writes knowledge graph nodes and edges to Neo4j
    Supports both APOC and pure Cypher approaches
    """
    
    def __init__(
        self,
        config: Config,
        nodes_file: str = "data/processed/nodes.csv",
        edges_file: str = "data/processed/edges.csv",
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        batch_size: int = 10000,
        use_apoc: bool = True
    ):
        """
        Initialize Neo4j writer
        
        Args:
            config: Configuration object
            nodes_file: Path to nodes CSV file
            edges_file: Path to edges CSV file
            neo4j_uri: Neo4j connection URI (overrides config)
            neo4j_user: Neo4j username (overrides config)
            neo4j_password: Neo4j password (overrides config)
            batch_size: Number of items per batch
            use_apoc: Whether to use APOC procedures (faster)
        """
        self.config = config
        self.nodes_file = Path(nodes_file)
        self.edges_file = Path(edges_file)
        
        # Use provided values or fall back to config
        self.neo4j_uri = neo4j_uri or NEO4J_URI
        self.neo4j_user = neo4j_user or NEO4J_USER
        self.neo4j_password = neo4j_password or NEO4J_PASSWORD
        
        self.batch_size = batch_size
        self.use_apoc = use_apoc
        
        # Initialize Neo4j driver using shared pattern
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            logger.info(f"✅ Connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.error(f"Cannot connect to Neo4j: {e}")
            raise
    
    def _run_query(self, query: str, params: Optional[Dict] = None) -> List:
        """
        Execute a Cypher query
        
        Args:
            query: Cypher query string
            params: Query parameters
        
        Returns:
            List of results
        """
        try:
            with self.driver.session() as session:
                result = list(session.run(query, params or {}))
                return result
        except Exception as e:
            logger.error(f"Query failed: {e}")
            logger.error(f"Query: {query[:200]}...")
            raise
    
    def _chunker(self, iterable, size: int):
        """
        Yield successive chunks from iterable
        
        Args:
            iterable: Input iterable
            size: Chunk size
        
        Yields:
            Chunks of specified size
        """
        batch = []
        for item in iterable:
            batch.append(item)
            if len(batch) >= size:
                yield batch
                batch = []
        if batch:
            yield batch
    
    def _apoc_available(self) -> bool:
        """
        Check if APOC is available
        
        Returns:
            True if APOC is installed
        """
        try:
            result = self._run_query("RETURN apoc.version() AS v")
            version = result[0]["v"]
            logger.info(f"APOC version: {version}")
            return True
        except Exception:
            logger.warning("APOC not available; falling back to pure Cypher")
            return False
    
    def create_constraints(self):
        """
        Create constraints and indexes in Neo4j
        """
        logger.info("Creating constraints...")
        try:
            self._run_query("""
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)
            logger.info("✅ Constraints created")
        except Exception as e:
            logger.warning(f"Constraint error: {e}")
    
    def clear_database(self):
        """
        Clear all nodes and relationships from the database
        WARNING: This will delete all data!
        """
        logger.warning("⚠️  Clearing all data from Neo4j database...")
        try:
            self._run_query("MATCH (n) DETACH DELETE n")
            logger.info("✅ Database cleared")
        except Exception as e:
            logger.error(f"Failed to clear database: {e}")
            raise
    
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
    
    def load_edges(self) -> List[Dict]:
        """
        Load edges from CSV file
        
        Returns:
            List of edge dictionaries
        """
        if not self.edges_file.exists():
            logger.error(f"Edges file not found: {self.edges_file}")
            return []
        
        edges = []
        with self.edges_file.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                edges.append(row)
        
        logger.info(f"Loaded {len(edges)} edges from {self.edges_file}")
        return edges
    
    def _write_nodes_apoc(self, rows: List[Dict]):
        """
        Write nodes using APOC (faster, dynamic labels)
        
        Args:
            rows: Batch of node dictionaries
        """
        query = """
        UNWIND $rows AS row
        WITH row,
             toInteger(row.id) AS id,
             row.name          AS name,
             row.label         AS label
        MERGE (e:Entity {id:id})
          ON CREATE SET e.name = name, e.label = label
          ON MATCH  SET e.name = name, e.label = label
        WITH e, label
        CALL apoc.create.addLabels(e, [label]) YIELD node
        RETURN count(*) AS c
        """
        self._run_query(query, {"rows": rows})
    
    def _write_nodes_noapoc(self, rows: List[Dict]):
        """
        Write nodes using pure Cypher (no APOC required)
        
        Args:
            rows: Batch of node dictionaries
        """
        query = """
        UNWIND $rows AS row
        WITH row,
             toInteger(row.id) AS id,
             row.name          AS name,
             row.label         AS label
        MERGE (e:Entity {id:id})
          ON CREATE SET e.name = name, e.label = label
          ON MATCH  SET e.name = name, e.label = label
        FOREACH (_ IN CASE WHEN label='SYMPTOM'         THEN [1] ELSE [] END | SET e:SYMPTOM)
        FOREACH (_ IN CASE WHEN label='CONDITION'       THEN [1] ELSE [] END | SET e:CONDITION)
        FOREACH (_ IN CASE WHEN label='COPING_STRATEGY' THEN [1] ELSE [] END | SET e:COPING_STRATEGY)
        FOREACH (_ IN CASE WHEN label='INTERVENTION'    THEN [1] ELSE [] END | SET e:INTERVENTION)
        FOREACH (_ IN CASE WHEN label='ISSUE'           THEN [1] ELSE [] END | SET e:ISSUE)
        FOREACH (_ IN CASE WHEN label='STRESSOR'        THEN [1] ELSE [] END | SET e:STRESSOR)
        FOREACH (_ IN CASE WHEN label='MEDICATION'      THEN [1] ELSE [] END | SET e:MEDICATION)
        RETURN count(*) AS c
        """
        self._run_query(query, {"rows": rows})
    
    def write_nodes(self, nodes: List[Dict]) -> bool:
        """
        Write nodes to Neo4j in batches
        
        Args:
            nodes: List of node dictionaries
        
        Returns:
            True if successful
        """
        if not nodes:
            logger.warning("No nodes to write")
            return False
        
        try:
            # Check APOC availability
            use_apoc = self.use_apoc and self._apoc_available()
            write_func = self._write_nodes_apoc if use_apoc else self._write_nodes_noapoc
            
            logger.info(f"Writing nodes using {'APOC' if use_apoc else 'pure Cypher'}...")
            
            total = 0
            for batch in self._chunker(nodes, self.batch_size):
                write_func(batch)
                total += len(batch)
                logger.info(f"[NODES] Imported {total}/{len(nodes)}")
            
            logger.info(f"✅ Successfully wrote {total} nodes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write nodes: {e}")
            return False
    
    def _write_edges_apoc(self, rows: List[Dict]):
        """
        Write edges using APOC (faster, dynamic relationship types)
        
        Args:
            rows: Batch of edge dictionaries
        """
        query = """
        UNWIND $rows AS row
        WITH toInteger(row.start_id) AS sid,
             toInteger(row.end_id)   AS tid,
             row.type                AS rtype,
             row.source_id           AS src
        MATCH (s:Entity {id:sid})
        MATCH (t:Entity {id:tid})
        WITH s, t, rtype,
             CASE WHEN src IS NULL OR trim(src)='' THEN []
                  ELSE [x IN split(src, ',') | toInteger(trim(x))]
             END AS src_list
        CALL apoc.create.relationship(s, rtype, {source_id: src_list}, t) YIELD rel
        RETURN count(*) AS c
        """
        self._run_query(query, {"rows": rows})
    
    def _write_edges_noapoc(self, rows: List[Dict]):
        """
        Write edges using pure Cypher (no APOC required)
        
        Args:
            rows: Batch of edge dictionaries
        """
        query = """
        UNWIND $rows AS row
        WITH toInteger(row.start_id) AS sid,
             toInteger(row.end_id)   AS tid,
             row.type                AS rtype,
             row.source_id           AS src
        MATCH (s:Entity {id:sid})
        MATCH (t:Entity {id:tid})
        WITH s, t, rtype,
             CASE WHEN src IS NULL OR trim(src)='' THEN []
                  ELSE [x IN split(src, ',') | toInteger(trim(x))]
             END AS src_list
        FOREACH (_ IN CASE WHEN rtype='TARGETS'                 THEN [1] ELSE [] END | MERGE (s)-[r:TARGETS]->(t)                 SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='ALLEVIATES'              THEN [1] ELSE [] END | MERGE (s)-[r:ALLEVIATES]->(t)              SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='TREATED_BY'              THEN [1] ELSE [] END | MERGE (s)-[r:TREATED_BY]->(t)              SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='HELPED_BY'               THEN [1] ELSE [] END | MERGE (s)-[r:HELPED_BY]->(t)               SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='MANAGED_BY'              THEN [1] ELSE [] END | MERGE (s)-[r:MANAGED_BY]->(t)              SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='SUGGESTS_STRATEGY'       THEN [1] ELSE [] END | MERGE (s)-[r:SUGGESTS_STRATEGY]->(t)       SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='REFERENCES_INTERVENTION' THEN [1] ELSE [] END | MERGE (s)-[r:REFERENCES_INTERVENTION]->(t) SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='RELATED_TO'              THEN [1] ELSE [] END | MERGE (s)-[r:RELATED_TO]->(t)              SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='WORSENED_BY'             THEN [1] ELSE [] END | MERGE (s)-[r:WORSENED_BY]->(t)             SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='TRIGGERED_BY'            THEN [1] ELSE [] END | MERGE (s)-[r:TRIGGERED_BY]->(t)            SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='HAS_FREQUENCY'           THEN [1] ELSE [] END | MERGE (s)-[r:HAS_FREQUENCY]->(t)           SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='HAS_DURATION'            THEN [1] ELSE [] END | MERGE (s)-[r:HAS_DURATION]->(t)            SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='HAS_SEVERITY'            THEN [1] ELSE [] END | MERGE (s)-[r:HAS_SEVERITY]->(t)            SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='OCCURRED_AT'             THEN [1] ELSE [] END | MERGE (s)-[r:OCCURRED_AT]->(t)             SET r.source_id=src_list)
        FOREACH (_ IN CASE WHEN rtype='NEGATES'                 THEN [1] ELSE [] END | MERGE (s)-[r:NEGATES]->(t)                 SET r.source_id=src_list)
        RETURN 0 AS _
        """
        self._run_query(query, {"rows": rows})
    
    def write_edges(self, edges: List[Dict]) -> bool:
        """
        Write edges to Neo4j in batches
        
        Args:
            edges: List of edge dictionaries
        
        Returns:
            True if successful
        """
        if not edges:
            logger.warning("No edges to write")
            return True  # Not an error
        
        try:
            # Check APOC availability
            use_apoc = self.use_apoc and self._apoc_available()
            write_func = self._write_edges_apoc if use_apoc else self._write_edges_noapoc
            
            logger.info(f"Writing edges using {'APOC' if use_apoc else 'pure Cypher'}...")
            
            total = 0
            for batch in self._chunker(edges, self.batch_size):
                write_func(batch)
                total += len(batch)
                logger.info(f"[EDGES] Imported {total}/{len(edges)}")
            
            logger.info(f"✅ Successfully wrote {total} edges")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write edges: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the graph in Neo4j
        
        Returns:
            Dictionary with node count, edge count, label distribution
        """
        try:
            stats = {}
            
            # Total node count
            result = self._run_query("MATCH (n) RETURN count(n) AS count")
            stats['node_count'] = result[0]['count']
            
            # Total edge count
            result = self._run_query("MATCH ()-[r]->() RETURN count(r) AS count")
            stats['edge_count'] = result[0]['count']
            
            # Label distribution
            result = self._run_query("""
                MATCH (n)
                UNWIND labels(n) AS label
                WITH label, count(*) AS count
                WHERE label <> 'Entity'
                RETURN label, count
                ORDER BY count DESC
            """)
            stats['labels'] = {row['label']: row['count'] for row in result}
            
            # Relationship type distribution
            result = self._run_query("""
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(*) AS count
                ORDER BY count DESC
            """)
            stats['relationship_types'] = {row['type']: row['count'] for row in result}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def run(self, clear_existing: bool = False) -> bool:
        """
        Run the complete Neo4j import pipeline
        
        Args:
            clear_existing: Whether to clear existing data first
        
        Returns:
            True if successful
        """
        logger.info("\n" + "=" * 60)
        logger.info("STARTING NEO4J IMPORT")
        logger.info("=" * 60)
        
        try:
            # Clear database if requested
            if clear_existing:
                self.clear_database()
            
            # Create constraints
            self.create_constraints()
            
            # Load data
            nodes = self.load_nodes()
            edges = self.load_edges()
            
            if not nodes:
                logger.error("No nodes to import")
                return False
            
            # Write nodes
            nodes_success = self.write_nodes(nodes)
            if not nodes_success:
                return False
            
            # Write edges
            edges_success = self.write_edges(edges)
            if not edges_success:
                return False
            
            # Get and display stats
            stats = self.get_stats()
            logger.info("\n" + "=" * 60)
            logger.info("NEO4J IMPORT COMPLETED")
            logger.info("=" * 60)
            logger.info(f"Total Nodes: {stats.get('node_count', 0)}")
            logger.info(f"Total Edges: {stats.get('edge_count', 0)}")
            
            if 'labels' in stats:
                logger.info("\nNode Labels:")
                for label, count in stats['labels'].items():
                    logger.info(f"  - {label}: {count}")
            
            if 'relationship_types' in stats:
                logger.info("\nRelationship Types:")
                for rel_type, count in stats['relationship_types'].items():
                    logger.info(f"  - {rel_type}: {count}")
            
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Neo4j import failed: {e}", exc_info=True)
            return False
    
    def close(self):
        """Close Neo4j driver connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
