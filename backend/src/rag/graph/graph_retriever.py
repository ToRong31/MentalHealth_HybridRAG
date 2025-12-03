"""
Graph Retriever Module
Chuyên xử lý logic expand subgraph và build context cho GraphRAG
"""
from typing import List, Dict, Any, Tuple

from .neo4j_client import expand_subgraph, get_node_names_from_neo4j


class GraphRetriever:
    """
    Chịu trách nhiệm expand subgraph từ anchor nodes
    và build context string cho LLM
    """
    
    def __init__(self):
        """Initialize Graph Retriever"""
        pass
    
    def retrieve_subgraph(self, anchor_ids: List[int]) -> Tuple[List, List]:
        """
        Expand subgraph từ anchor nodes
        
        Args:
            anchor_ids: List of node IDs làm anchors
        
        Returns:
            Tuple of (nodes, relationships)
        """
        if not anchor_ids:
            return [], []
        
        nodes, rels = expand_subgraph(anchor_ids)
        return nodes, rels
    
    def build_context(
        self, 
        nodes: List, 
        rels: List, 
        anchors: List[Dict[str, Any]]
    ) -> str:
        """
        Build context string from subgraph for LLM
        
        Args:
            nodes: List of Neo4j nodes
            rels: List of Neo4j relationships
            anchors: List of anchor dicts with 'node_id'
        
        Returns:
            Formatted context string in format:
            TRIPLES
            source_name -[REL_TYPE]-> target_name {src:X}
        """
        if not nodes:
            return ""
        
        # Build node map
        node_map: Dict[int, Dict[str, Any]] = {}
        for n in nodes:
            labels = list(n.labels) if n.labels else ["Entity"]
            # Get primary label (first one)
            primary_label = labels[0] if labels else "Entity"
            name = n.get("name") or n.get("label") or f"Node_{n.id}"
            business_id = n.get("id")
            
            node_map[n.id] = {
                "neo_id": n.id,
                "business_id": business_id,
                "name": name,
                "label": primary_label,
                "props": dict(n),
            }
        
        # Build context in TRIPLES format
        lines = ["TRIPLES"]
        
        # Format all relationships as triples
        processed_rels = set()
        for r in rels:
            s_id = r.start_node.id
            o_id = r.end_node.id
            rel_type = r.type
            
            # Avoid duplicates
            rel_key = (s_id, rel_type, o_id)
            if rel_key in processed_rels:
                continue
            processed_rels.add(rel_key)
            
            src_info = node_map.get(s_id)
            tgt_info = node_map.get(o_id)
            
            if not src_info or not tgt_info:
                continue
            
            # Get source_id from relationship properties
            rel_props = dict(r)
            source_list = rel_props.get("source_id", [])
            
            # Format source_id
            if isinstance(source_list, list) and source_list:
                source_str = ",".join(map(str, source_list))
            elif source_list:
                source_str = str(source_list)
            else:
                source_str = "?"
            
            # Format triple: source_name -[REL_TYPE]-> target_name {src:X}
            src_name = src_info["name"]
            tgt_name = tgt_info["name"]
            
            triple_line = (
                f"{src_name} "
                f"-[{rel_type}]-> "
                f"{tgt_name} {{src:{source_str}}}"
            )
            lines.append(triple_line)
        
        return "\n".join(lines)


# Global instance
graph_retriever = GraphRetriever()

