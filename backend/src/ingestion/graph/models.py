"""
Data models for knowledge graph building
"""
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Config:
    """Configuration for graph building"""
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 5.0
    min_delay_between_calls: float = 5.0
    batch_delay: float = 20.0  # Delay between batches to avoid rate limits
    rate_limit_delay: float = 60.0  # Delay for 429 errors
    model_name: str = "gemini-2.5-flash-lite"
    temperature: float = 0.2


@dataclass
class GraphData:
    """Store extracted nodes and edges"""
    nodes: List[Dict[str, str]]
    edges: List[Dict[str, str]]


@dataclass
class Node:
    """Represents a node in the knowledge graph"""
    id: str
    name: str
    label: str


@dataclass
class Edge:
    """Represents an edge in the knowledge graph"""
    start_id: str
    end_id: str
    type: str
    source_id: str

