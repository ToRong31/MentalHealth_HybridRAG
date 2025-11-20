"""
Base Retriever Interface
Định nghĩa interface chung cho tất cả retrievers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseRetriever(ABC):
    """
    Base abstract class for all retrievers
    Mọi retriever (graph, dense, hybrid) đều implement interface này
    """
    
    @abstractmethod
    def retrieve(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Retrieve context based on query
        
        Args:
            query: User's question
            **kwargs: Additional parameters
        
        Returns:
            Dictionary containing:
                - context: str (formatted context for LLM)
                - metadata: Dict (additional info like anchors, scores, etc.)
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Return retriever name for logging/debugging
        
        Returns:
            Retriever name
        """
        pass


class RetrievalResult:
    """
    Standard result format for all retrievers
    """
    
    def __init__(
        self,
        context: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize retrieval result
        
        Args:
            context: Formatted context string for LLM
            metadata: Additional metadata (anchors, scores, source, etc.)
        """
        self.context = context
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "context": self.context,
            "metadata": self.metadata
        }
    
    def __repr__(self) -> str:
        return f"RetrievalResult(context_len={len(self.context)}, metadata={self.metadata})"

