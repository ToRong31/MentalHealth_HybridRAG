"""
Knowledge Graph Builder for Mental Health Data
Extracts nodes and edges from JSON input using Google Generative AI
"""
import os
import json
import csv
import time
import argparse
import logging
import yaml
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from api_key_manager import APIKeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for graph building"""
    batch_size: int = 5
    max_retries: int = 3
    retry_delay: float = 5.0
    min_delay_between_calls: float = 5.0
    batch_delay: float = 15.0  # Delay between batches to avoid rate limits
    rate_limit_delay: float = 60.0  # Delay for 429 errors
    model_name: str = "gemini-2.5-flash-lite"
    temperature: float = 0.0


@dataclass
class GraphData:
    """Store extracted nodes and edges"""
    nodes: List[Dict[str, str]]
    edges: List[Dict[str, str]]


class GraphBuilder:
    """
    Main class for building knowledge graph from mental health data
    """
    
    def __init__(self, config: Config, api_key_manager: APIKeyManager):
        self.config = config
        self.api_manager = api_key_manager
        self.node_cache: Dict[str, str] = {}  # name -> id mapping for O(1) lookup
        self.processed_ids: Set[str] = set()
        self.error_ids: Set[str] = set()
        
        # Files - using Output directory
        self.nodes_file = "Output/nodes.csv"
        self.edges_file = "Output/edges.csv"
        self.processed_file = "Output/processed_id.txt"
        self.errors_file = "Output/errors_id.txt"
        
        # Ensure Output directory exists
        os.makedirs("Output", exist_ok=True)
        
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
        """Load prompt template from config/prompt.yaml"""
        config_path = "config/prompt.yaml"
        
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"Required config file missing: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            prompt = config.get('batch_prompt', '')
            if not prompt:
                raise ValueError("'batch_prompt' not found in config file")
            
            logger.info("Successfully loaded prompt from config/prompt.yaml")
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
                
                # Clear the errors file after loading to avoid duplicate retries
                # If retry fails, IDs will be written back to this file
                with open(self.errors_file, 'w', encoding='utf-8') as f:
                    pass  # Empty the file
                logger.info(f"Cleared {self.errors_file} (will be repopulated if retries fail)")
    
    def load_input_data(self, input_file: str, index_filter: Optional[str] = None) -> List[Dict]:
        """
        Load input JSON data with filtering
        
        Args:
            input_file: Path to input JSON file
            index_filter: Filter string like "1-10" or "5,10,15"
        
        Returns:
            List of filtered input data
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Apply index filter if provided
        if index_filter:
            filtered_data = self._apply_index_filter(data, index_filter)
        else:
            filtered_data = data
        
        # Filter out already processed (unless they're in error list)
        final_data = []
        for item in filtered_data:
            item_id = str(item['id'])
            if item_id in self.error_ids:
                # Include error IDs for retry
                final_data.append(item)
            elif item_id not in self.processed_ids:
                # Include unprocessed IDs
                final_data.append(item)
        
        logger.info(f"Loaded {len(final_data)} items to process (filtered from {len(data)} total)")
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
    
    def process_batch(self, batch: List[Dict], batch_num: int, total_batches: int) -> bool:
        """
        Process a batch of items
        
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
                
                # Mark success (resets error count for this key)
                # Note: Key rotation already happened in get_next_key()
                self.api_manager.mark_success(api_key)
                self._mark_processed(batch_ids)
                
                logger.info(
                    f"✓ Batch {batch_num} completed: "
                    f"{len(graph_data.edges)} edges extracted"
                )
                return True
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Attempt {attempt}/{self.config.max_retries} failed: {error_msg}")
                
                # Handle API errors
                # Note: Key rotation already happened in get_next_key()
                # handle_error() only updates error stats and may ban the key
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
                    logger.error(f"✗ Batch {batch_num} failed after {self.config.max_retries} attempts")
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
        seen_edges = set()  # Track edges (start_id, end_id, type) to avoid duplicates in batch
        new_node_count = 0
        duplicate_node_count = 0
        self_loop_count = 0  # Track self-loops skipped
        duplicate_edge_count = 0  # Track duplicate edges in batch
        
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
                # e.g., {SYMPTOM} -> SYMPTOM
                node_label = node_label.strip('{}')
                
                if not node_name:
                    continue
                
                node_id, is_new = self._get_or_create_node_id(node_name)
                
                # Track statistics
                if is_new:
                    new_node_count += 1
                else:
                    duplicate_node_count += 1
                    logger.debug(f"♻️  Reusing existing node: '{node_name}' (ID: {node_id})")
                
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
                
                # Skip self-loops (node pointing to itself)
                if start_id == end_id:
                    self_loop_count += 1
                    logger.debug(f"⚠️  Skipped self-loop: '{start_name}' → '{start_name}' (ID: {start_id})")
                    continue
                
                # Check for duplicate edges in this batch
                edge_key = (start_id, end_id, edge_type)
                if edge_key in seen_edges:
                    duplicate_edge_count += 1
                    logger.debug(f"🔄 Skipped duplicate edge in batch: {start_id} → {end_id} ({edge_type})")
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
            f"📊 Node statistics: {new_node_count} new, "
            f"{duplicate_node_count} duplicates (reused)"
        )
        if self_loop_count > 0:
            logger.info(f"⚠️  Skipped {self_loop_count} self-loop edges")
        if duplicate_edge_count > 0:
            logger.info(f"🔄 Skipped {duplicate_edge_count} duplicate edges in batch")
        
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
                    f"💾 Saved to CSV: {nodes_saved} new nodes added, "
                    f"{nodes_skipped} already in file (skipped)"
                )
        
        # Save edges (always append)
        if graph_data.edges:
            with open(self.edges_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['start_id', 'end_id', 'type', 'source_id'])
                writer.writerows(graph_data.edges)
            logger.info(f"💾 Saved {len(graph_data.edges)} edges to CSV")
    
    def _mark_processed(self, ids: List[str]):
        """Mark IDs as processed"""
        with open(self.processed_file, 'a', encoding='utf-8') as f:
            for id_val in ids:
                f.write(f"{id_val}\n")
                self.processed_ids.add(id_val)
                # Remove from error list if present
                self.error_ids.discard(id_val)
    
    def _mark_error(self, ids: List[str]):
        """Mark IDs as error"""
        with open(self.errors_file, 'a', encoding='utf-8') as f:
            for id_val in ids:
                if id_val not in self.error_ids:
                    f.write(f"{id_val}\n")
                    self.error_ids.add(id_val)
    
    def run(self, input_data: List[Dict]):
        """
        Main execution loop
        
        Args:
            input_data: List of input items to process
        """
        if not input_data:
            logger.warning("No data to process")
            return
        
        # Create batches
        batches = [
            input_data[i:i + self.config.batch_size]
            for i in range(0, len(input_data), self.config.batch_size)
        ]
        
        total_batches = len(batches)
        completed_batches = 0
        error_batches = 0
        
        logger.info("=" * 60)
        logger.info(f"Starting graph building process")
        logger.info(f"Total items: {len(input_data)}")
        logger.info(f"Batch size: {self.config.batch_size}")
        logger.info(f"Total batches: {total_batches}")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Process each batch
        for i, batch in enumerate(batches, 1):
            success = self.process_batch(batch, i, total_batches)
            
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
            
            # Delay between batches to avoid rate limits
            if i < total_batches:
                logger.info(f"⏳ Waiting {self.config.batch_delay}s before next batch...")
                time.sleep(self.config.batch_delay)
        
        # Final summary
        elapsed_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"Processing completed in {elapsed_time:.1f} seconds")
        logger.info(f"Batches completed: {completed_batches}/{total_batches}")
        logger.info(f"Batches with errors: {error_batches}/{total_batches}")
        logger.info(f"Total nodes in cache: {len(self.node_cache)}")
        logger.info("=" * 60)
        
        # API Manager summary
        self.api_manager.print_summary()


def load_api_keys(api_file: str, key_range: Optional[str] = None) -> List[str]:
    """
    Load API keys from file with optional range filter
    
    Args:
        api_file: Path to API key file (one key per line)
        key_range: Range like "1-20" or "5,10,15"
    
    Returns:
        List of API keys
    """
    with open(api_file, 'r', encoding='utf-8') as f:
        all_keys = [line.strip() for line in f if line.strip()]
    
    if not key_range:
        return all_keys
    
    # Parse range
    indices = set()
    parts = key_range.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            indices.update(range(int(start) - 1, int(end)))  # Convert to 0-indexed
        else:
            indices.add(int(part) - 1)  # Convert to 0-indexed
    
    selected_keys = [all_keys[i] for i in sorted(indices) if i < len(all_keys)]
    logger.info(f"Loaded {len(selected_keys)} API keys from range '{key_range}'")
    return selected_keys


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Build knowledge graph from mental health data"
    )
    
    parser.add_argument(
        '--input',
        type=str,
        default='Input/input.json',
        help='Input JSON file path (default: Input/input.json)'
    )
    
    parser.add_argument(
        '--api',
        type=str,
        help='API key range (e.g., "1-20" or "5,10,15") from api_key.txt'
    )
    
    parser.add_argument(
        '--api-file',
        type=str,
        default='Input/api_key.txt',
        help='API key file path (default: Input/api_key.txt)'
    )
    
    parser.add_argument(
        '--index',
        type=str,
        help='Index filter for input data (e.g., "1-100" or "5,10,15")'
    )
    
    parser.add_argument(
        '--batch',
        type=int,
        default=5,
        help='Batch size (default: 5)'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum retries per batch (default: 3)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gemini-2.5-flash-lite',
        help='Google Generative AI model name (default: gemini-2.5-flash-lite)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Load API keys
    try:
        api_keys = load_api_keys(args.api_file, args.api)
        if not api_keys:
            logger.error("No API keys loaded. Please check api_key.txt file.")
            return
    except FileNotFoundError:
        logger.error(f"API key file '{args.api_file}' not found.")
        return
    except Exception as e:
        logger.error(f"Error loading API keys: {e}")
        return
    
    # Initialize configuration
    config = Config(
        batch_size=args.batch,
        max_retries=args.max_retries,
        model_name=args.model
    )
    
    # Initialize API Key Manager
    api_manager = APIKeyManager(api_keys, min_delay_between_calls=config.min_delay_between_calls)
    
    # Initialize Graph Builder
    builder = GraphBuilder(config, api_manager)
    
    # Load processed and error IDs
    builder.load_processed_and_errors()
    
    # Load input data
    try:
        input_data = builder.load_input_data(args.input, args.index)
    except FileNotFoundError:
        logger.error(f"Input file '{args.input}' not found.")
        return
    except Exception as e:
        logger.error(f"Error loading input data: {e}")
        return
    
    # Run the builder
    builder.run(input_data)


if __name__ == "__main__":
    main()

