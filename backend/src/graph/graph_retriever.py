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
            Formatted context string
        """
        # Build node map
        node_map: Dict[int, Dict[str, Any]] = {}
        for n in nodes:
            labels = list(n.labels) if n.labels else []
            name = n.get("name") or n.get("label") or f"Node_{n.id}"
            node_map[n.id] = {
                "neo_id": n.id,
                "id": n.get("id"),
                "name": name,
                "labels": labels,
                "props": dict(n),
            }
        
        # Build adjacency list
        adjacency: Dict[int, List[Dict[str, Any]]] = {
            nid: [] for nid in node_map.keys()
        }
        
        for r in rels:
            s_id = r.start_node.id
            o_id = r.end_node.id
            rel_type = r.type
            rel_props = dict(r)
            
            # Outgoing edge from source
            adjacency[s_id].append({
                "direction": "out",
                "rel_type": rel_type,
                "target_id": o_id,
                "props": rel_props,
            })
            
            # Incoming edge to target
            adjacency[o_id].append({
                "direction": "in",
                "rel_type": rel_type,
                "target_id": s_id,
                "props": rel_props,
            })
        
        # Identify anchor nodes
        anchor_business_ids = {a["node_id"] for a in anchors}
        anchor_internal_ids = []
        for neo_id, info in node_map.items():
            if info["id"] in anchor_business_ids:
                anchor_internal_ids.append(neo_id)
        
        # Format context
        lines: List[str] = []
        
        # Format anchor nodes first
        for neo_id in anchor_internal_ids:
            info = node_map[neo_id]
            lines.append(self._format_node_header(info, role="ANCHOR"))
            
            for rel in adjacency.get(neo_id, []):
                tgt_info = node_map.get(rel["target_id"])
                if tgt_info:
                    lines.append(self._format_rel_entry(info, rel, tgt_info))
            
            lines.append("")
        
        # Format other connected nodes
        other_ids = [nid for nid in node_map.keys() if nid not in anchor_internal_ids]
        if other_ids:
            lines.append("Other connected nodes:")
            for neo_id in other_ids:
                info = node_map[neo_id]
                lines.append(self._format_node_header(info, role="NEIGHBOR"))
                
                for rel in adjacency.get(neo_id, []):
                    tgt_info = node_map.get(rel["target_id"])
                    if tgt_info:
                        lines.append(self._format_rel_entry(info, rel, tgt_info))
                
                lines.append("")
        
        return "\n".join(lines).strip()
    
    def _format_node_header(self, info: Dict[str, Any], role: str) -> str:
        """Format node header line"""
        labels_str = ",".join(info["labels"]) if info["labels"] else "Entity"
        return (
            f"[{role}] {info['name']} "
            f"({labels_str}, business_id={info['id']}, neo_id={info['neo_id']})"
        )
    
    def _format_rel_entry(
        self, 
        src_info: Dict[str, Any], 
        rel: Dict[str, Any], 
        tgt_info: Dict[str, Any]
    ) -> str:
        """Format relationship entry line"""
        direction_symbol = "->" if rel["direction"] == "out" else "<-"
        rel_type = rel["rel_type"]
        props = rel["props"]
        source_id = props.get("source_id")
        
        labels_str = ",".join(tgt_info["labels"]) if tgt_info["labels"] else "Entity"
        base = (
            f"  - {rel_type} {direction_symbol} "
            f"{tgt_info['name']} ({labels_str}, business_id={tgt_info['id']})"
        )
        
        if source_id is not None:
            base += f" [source_id={source_id}]"
        
        return base


# Global instance
graph_retriever = GraphRetriever()

