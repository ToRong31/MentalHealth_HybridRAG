"""
LLM-based Knowledge Graph Extractor
Extracts nodes and edges from text using Google Generative AI
"""
import os
import json
import csv
import time
import logging
import yaml
import re
from typing import List, Dict, Set, Tuple, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from .models import Config, GraphData
from .api_key_manager import APIKeyManager

logger = logging.getLogger(__name__)


class GraphExtractor:
    """
    Extracts knowledge graph elements (nodes and edges) from text using LLM
    """
    
    def __init__(self, config: Config, api_key_manager: APIKeyManager):
        """
        Initialize GraphExtractor
        
        Args:
            config: Configuration object
            api_key_manager: API key manager for handling multiple keys
        """
        self.config = config
        self.api_manager = api_key_manager
        self.node_cache: Dict[str, str] = {}  # name -> id mapping for O(1) lookup
        self.processed_ids: Set[str] = set()
        self.error_ids: Set[str] = set()
        
        # Files - using data/processed directory
        self.output_dir = "data/processed"
        os.makedirs(self.output_dir, exist_ok=True)
        self.nodes_file = os.path.join(self.output_dir, "nodes.csv")
        self.edges_file = os.path.join(self.output_dir, "edges.csv")
        self.processed_file = os.path.join(self.output_dir, "processed_id.txt")
        self.errors_file = os.path.join(self.output_dir, "errors_id.txt")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize CSV files if they don't exist
        self._initialize_csv_files()
        
        # Load existing nodes into cache
        self._load_existing_nodes()
        
        # Load prompt template from config file
        self.prompt_text = self._load_prompt_from_config()
        
        # Create simple prompt template (user message only, no system message)
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("user", self.prompt_text)
        ])
    
    def _load_prompt_from_config(self) -> str:
        """Load prompt template from config file"""
        # Default path in ingestion module
        config_path = "src/rag/ingestion/graph/promts/graph_extraction_prompt.yaml"
        
        if not os.path.exists(config_path):
            logger.error(f"Prompt config file not found: {config_path}")
            raise FileNotFoundError(f"Required prompt config file missing: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            prompt = config.get('batch_prompt', '')
            if not prompt:
                raise ValueError("'batch_prompt' not found in config file")
            
            logger.info(f"Successfully loaded prompt from {config_path}")
            return prompt
            
        except Exception as e:
            logger.error(f"Error loading prompt config: {e}")
            raise
    
    def _initialize_csv_files(self):
        """Initialize CSV files with headers if they don't exist"""
        if not os.path.exists(self.nodes_file):
            with open(self.nodes_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['id', 'name', 'label'])
                writer.writeheader()
            logger.info(f"Created {self.nodes_file}")
        
        if not os.path.exists(self.edges_file):
            with open(self.edges_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['start_id', 'end_id', 'type', 'source_id'])
                writer.writeheader()
            logger.info(f"Created {self.edges_file}")
    
    def _load_existing_nodes(self):
        """Load existing nodes into cache for O(1) duplicate checking"""
        if not os.path.exists(self.nodes_file):
            return
        
        with open(self.nodes_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map node name to its ID
                self.node_cache[row['name'].lower()] = row['id']
        
        logger.info(f"Loaded {len(self.node_cache)} existing nodes into cache")
    
    def _get_or_create_node_id(self, node_name: str) -> Tuple[str, bool]:
        """
        Get existing node ID or create new one (O(1) lookup)
        
        Args:
            node_name: Name of the node
        
        Returns:
            Tuple of (Node ID, is_new_node)
        """
        node_key = node_name.lower()
        if node_key in self.node_cache:
            return self.node_cache[node_key], False  # Existing node
        else:
            # Create new ID - simple integer
            new_id = str(len(self.node_cache) + 1)
            self.node_cache[node_key] = new_id
            return new_id, True  # New node
    
    def extract_from_batch(self, batch: List[Dict], batch_num: int, total_batches: int) -> bool:
        """
        Extract knowledge graph from a batch of text items
        
        Args:
            batch: List of items to process
            batch_num: Current batch number
            total_batches: Total number of batches
        
        Returns:
            True if successful, False if failed after retries
        """
        batch_ids = [str(item['id']) for item in batch]
        
        # Format batch text according to prompt format: "- [idx] <text>"
        batch_text = "\n\n".join([
            f"- [{item['id']}] {item['answer']}"
            for item in batch
        ])
        
        logger.info(f"Processing batch {batch_num}/{total_batches} (IDs: {', '.join(batch_ids)})")
        
        for attempt in range(1, self.config.max_retries + 1):
            try:
                # Get API key and create LLM
                api_key = self.api_manager.get_next_key()
                llm = ChatGoogleGenerativeAI(
                    model=self.config.model_name,
                    google_api_key=api_key,
                    temperature=self.config.temperature,
                    max_retries=0
                )
                
                # Create chain and invoke
                chain = self.prompt_template | llm
                response = chain.invoke({"text_block": batch_text})
                
                # Parse response
                graph_data = self._parse_llm_response(response.content, batch_ids)
                
                # Save to CSV
                self._save_graph_data(graph_data, batch_ids)
                
                # Mark success
                self.api_manager.mark_success(api_key)
                self._mark_processed(batch_ids)
                
                logger.info(
                    f"[OK] Batch {batch_num} completed: "
                    f"{len(graph_data.edges)} edges extracted"
                )
                return True
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Attempt {attempt}/{self.config.max_retries} failed: {error_msg}")
                
                # Handle API errors
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    self.api_manager.handle_error(api_key, 429, error_msg)
                    logger.warning(f"Rate limit hit, waiting {self.config.rate_limit_delay}s...")
                    time.sleep(self.config.rate_limit_delay)
                elif "401" in error_msg or "403" in error_msg:
                    status_code = 401 if "401" in error_msg else 403
                    self.api_manager.handle_error(api_key, status_code, error_msg)
                else:
                    # Other errors
                    logger.error(f"Unknown error: {error_msg}")
                
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                else:
                    # Max retries exceeded
                    logger.error(f"[X] Batch {batch_num} failed after {self.config.max_retries} attempts")
                    self._mark_error(batch_ids)
                    return False
        
        return False
    
    def _parse_llm_response(self, response_text: str, source_ids: List[str]) -> GraphData:
        """
        Parse LLM response to extract nodes and edges
        
        Args:
            response_text: Raw LLM response (expected to be JSON array)
            source_ids: Source IDs for this batch
        
        Returns:
            GraphData object
        """
        # Clean response text - remove markdown code fences if present
        cleaned_text = response_text.strip()
        if cleaned_text.startswith('```'):
            # Remove code fence markers
            lines = cleaned_text.split('\n')
            cleaned_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else cleaned_text
        
        # Try to extract JSON array from response
        # Look for array starting with [ and ending with ]
        json_match = re.search(r'\[[\s\S]*\]', cleaned_text)
        if not json_match:
            logger.warning("No JSON array found in response, returning empty graph")
            return GraphData(nodes=[], edges=[])
        
        try:
            data_array = json.loads(json_match.group())
            if not isinstance(data_array, list):
                logger.warning("Response is not a JSON array, returning empty graph")
                return GraphData(nodes=[], edges=[])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Problematic text: {json_match.group()[:200]}...")
            return GraphData(nodes=[], edges=[])
        
        all_nodes = []
        all_edges = []
        seen_nodes = set()  # Track node IDs we've already added
        seen_edges = set()  # Track edges to avoid duplicates
        new_node_count = 0
        duplicate_node_count = 0
        self_loop_count = 0
        duplicate_edge_count = 0
        
        # Process each extraction result in the array
        for extraction in data_array:
            if not isinstance(extraction, dict):
                continue
            
            source_idx = str(extraction.get('source_index', ''))
            
            # Process nodes
            for node_data in extraction.get('nodes', []):
                node_name = node_data.get('name', '').strip()
                node_label = node_data.get('label', 'Entity').strip()
                
                # Remove curly braces from label if present
                node_label = node_label.strip('{}')
                
                if not node_name:
                    continue
                
                node_id, is_new = self._get_or_create_node_id(node_name)
                
                # Track statistics
                if is_new:
                    new_node_count += 1
                else:
                    duplicate_node_count += 1
                    logger.debug(f"[REUSE] Reusing existing node: '{node_name}' (ID: {node_id})")
                
                # Only add if we haven't seen this node in this batch yet
                if node_id not in seen_nodes:
                    all_nodes.append({
                        'id': node_id,
                        'name': node_name,
                        'label': node_label
                    })
                    seen_nodes.add(node_id)
            
            # Process edges
            for edge_data in extraction.get('edges', []):
                start_name = edge_data.get('start', '').strip()
                end_name = edge_data.get('end', '').strip()
                edge_type = edge_data.get('type', 'RELATES_TO').strip()
                
                # Remove curly braces from edge type if present
                edge_type = edge_type.strip('{}')
                
                if not start_name or not end_name:
                    continue
                
                start_id, _ = self._get_or_create_node_id(start_name)
                end_id, _ = self._get_or_create_node_id(end_name)
                
                # Skip self-loops
                if start_id == end_id:
                    self_loop_count += 1
                    logger.debug(f"[WARN] Skipped self-loop: '{start_name}' (ID: {start_id})")
                    continue
                
                # Check for duplicate edges in this batch
                edge_key = (start_id, end_id, edge_type)
                if edge_key in seen_edges:
                    duplicate_edge_count += 1
                    logger.debug(f"[SKIP] Skipped duplicate edge: {start_id} -> {end_id} ({edge_type})")
                    continue
                
                seen_edges.add(edge_key)
                all_edges.append({
                    'start_id': start_id,
                    'end_id': end_id,
                    'type': edge_type,
                    'source_id': source_idx if source_idx else ','.join(source_ids)
                })
        
        # Log summary
        logger.info(
            f"[STATS] Node statistics: {new_node_count} new, "
            f"{duplicate_node_count} duplicates (reused)"
        )
        if self_loop_count > 0:
            logger.info(f"[WARN] Skipped {self_loop_count} self-loop edges")
        if duplicate_edge_count > 0:
            logger.info(f"[SKIP] Skipped {duplicate_edge_count} duplicate edges in batch")
        
        return GraphData(nodes=all_nodes, edges=all_edges)
    
    def _save_graph_data(self, graph_data: GraphData, source_ids: List[str]):
        """
        Save graph data to CSV files
        
        Args:
            graph_data: GraphData to save
            source_ids: Source IDs for tracking
        """
        # Save nodes (only new ones)
        nodes_saved = 0
        nodes_skipped = 0
        
        if graph_data.nodes:
            existing_ids = set()
            if os.path.exists(self.nodes_file):
                with open(self.nodes_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    existing_ids = {row['id'] for row in reader}
            
            new_nodes = [n for n in graph_data.nodes if n['id'] not in existing_ids]
            nodes_skipped = len(graph_data.nodes) - len(new_nodes)
            
            if new_nodes:
                with open(self.nodes_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['id', 'name', 'label'])
                    writer.writerows(new_nodes)
                nodes_saved = len(new_nodes)
            
            # Log detailed statistics
            if nodes_saved > 0 or nodes_skipped > 0:
                logger.info(
                    f"[SAVED] Saved to CSV: {nodes_saved} new nodes added, "
                    f"{nodes_skipped} already in file (skipped)"
                )
        
        # Save edges (always append)
        if graph_data.edges:
            with open(self.edges_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['start_id', 'end_id', 'type', 'source_id'])
                writer.writerows(graph_data.edges)
            logger.info(f"[SAVED] Saved {len(graph_data.edges)} edges to CSV")
    


    def _mark_processed(self, ids: List[str]):
        """Mark IDs as processed"""
        try:
            logger.info(f"[MARK_PROCESSED] Marking {len(ids)} IDs as processed: {ids}")
            logger.info(f"[MARK_PROCESSED] processed_file = {os.path.abspath(self.processed_file)}")

            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(self.processed_file), exist_ok=True)

            with open(self.processed_file, 'a', encoding='utf-8') as f:
                for id_val in ids:
                    f.write(f"{id_val}\n")
                    self.processed_ids.add(id_val)
                    # Remove from error list if present
                    self.error_ids.discard(id_val)

            logger.info(f"[MARK_PROCESSED] Done writing {len(ids)} IDs")

        except Exception as e:
            logger.error(f"[MARK_PROCESSED] Failed to write processed IDs: {e}")


    def _mark_error(self, ids: List[str]):
        """Mark IDs as error"""
        try:
            logger.info(f"[MARK_ERROR] Marking {len(ids)} IDs as error: {ids}")
            logger.info(f"[MARK_ERROR] errors_file = {os.path.abspath(self.errors_file)}")

            os.makedirs(os.path.dirname(self.errors_file), exist_ok=True)

            with open(self.errors_file, 'a', encoding='utf-8') as f:
                for id_val in ids:
                    if id_val not in self.error_ids:
                        f.write(f"{id_val}\n")
                        self.error_ids.add(id_val)

            logger.info(f"[MARK_ERROR] Done writing error IDs")

        except Exception as e:
            logger.error(f"[MARK_ERROR] Failed to write error IDs: {e}")

    
    def load_processed_and_errors(self):
        """Load previously processed IDs and error IDs"""
        # Load processed IDs
        if os.path.exists(self.processed_file):
            with open(self.processed_file, 'r', encoding='utf-8') as f:
                self.processed_ids = set(line.strip() for line in f if line.strip())
            logger.info(f"Loaded {len(self.processed_ids)} processed IDs")
        
        # Load error IDs (these should be retried)
        if os.path.exists(self.errors_file):
            with open(self.errors_file, 'r', encoding='utf-8') as f:
                self.error_ids = set(line.strip() for line in f if line.strip())
            
            if self.error_ids:
                logger.info(f"Loaded {len(self.error_ids)} error IDs to retry")
                
                # Clear the errors file after loading
                with open(self.errors_file, 'w', encoding='utf-8') as f:
                    pass
                logger.info(f"Cleared {self.errors_file} (will be repopulated if retries fail)")
    
    def get_stats(self) -> dict:
        """Get extraction statistics"""
        return {
            "total_nodes": len(self.node_cache),
            "processed_ids": len(self.processed_ids),
            "error_ids": len(self.error_ids)
        }

