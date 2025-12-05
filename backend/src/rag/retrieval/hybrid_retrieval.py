"""
Hybrid Retriever Implementation
Combines dense and graph retrieval by executing them concurrently
"""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from .base_retrieval import BaseRetrieval, RetrievalResult
from .graph_retrieval import graph_retrieval
from .dense_retrieval import dense_retrieval

logger = logging.getLogger(__name__)

# Create a dedicated thread pool for hybrid retrieval
# Use more workers to allow true parallel execution of sync calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hybrid_retrieval")


class HybridRetrieval(BaseRetrieval):
    """
    Hybrid retrieval that combines dense and graph retrieval.
    Executes both retrievals concurrently using asyncio.gather() for better performance.
    """
    
    def __init__(
        self,
        graph_retriever: Optional[BaseRetrieval] = None,
        dense_retriever: Optional[BaseRetrieval] = None,
        combine_strategy: str = "concatenate"
    ):
        """
        Initialize hybrid retriever
        
        Args:
            graph_retriever: Graph retrieval instance (default: global graph_retrieval)
            dense_retriever: Dense retrieval instance (default: global dense_retrieval)
            combine_strategy: How to combine contexts ("concatenate" or "weighted")
        """
        self.graph_retrieval = graph_retriever or graph_retrieval
        self.dense_retrieval = dense_retriever or dense_retrieval
        self.combine_strategy = combine_strategy
    
    def retrieve(self, query: str, **kwargs) -> RetrievalResult:
        """
        Synchronous retrieve (runs async version in event loop)
        
        Args:
            query: User's question
            **kwargs: Additional parameters
        
        Returns:
            RetrievalResult with combined context
        """
        # Run async version in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.retrieve_async(query, **kwargs))
    
    async def retrieve_async(self, query: str, **kwargs) -> RetrievalResult:
        """
        Async retrieve that runs both retrievers in parallel
        
        Args:
            query: User's question
            **kwargs: Additional parameters (can include graph_kwargs, dense_kwargs)
        
        Returns:
            RetrievalResult with combined context and metadata from both
        """
        start_time = time.time()
        
        # Extract specific kwargs for each retriever
        graph_kwargs = kwargs.get('graph_kwargs', {})
        dense_kwargs = kwargs.get('dense_kwargs', {})
        
        logger.info(f"Starting hybrid retrieval for query: {query[:50]}...")
        
        # Run both retrievers concurrently using dedicated executor
        try:
            loop = asyncio.get_event_loop()
            
            # Run both in parallel using our dedicated thread pool
            graph_task = loop.run_in_executor(
                _executor,
                lambda: self.graph_retrieval.retrieve(query, **graph_kwargs)
            )
            dense_task = loop.run_in_executor(
                _executor,
                lambda: self.dense_retrieval.retrieve(query, **dense_kwargs)
            )
            
            graph_result, dense_result = await asyncio.gather(
                graph_task,
                dense_task,
                return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(graph_result, Exception):
                logger.error(f"Graph retrieval failed: {graph_result}")
                graph_result = RetrievalResult(context="", metadata={"error": str(graph_result)})
            
            if isinstance(dense_result, Exception):
                logger.error(f"Dense retrieval failed: {dense_result}")
                dense_result = RetrievalResult(context="", metadata={"error": str(dense_result)})
            
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            return RetrievalResult(
                context="",
                metadata={"error": str(e), "retriever": self.get_name()}
            )
        
        elapsed_time = time.time() - start_time
        
        # Debug: Log context lengths
        logger.info(f"Graph context length: {len(graph_result.context)} chars")
        logger.info(f"Dense context length: {len(dense_result.context)} chars")
        
        # Combine contexts
        combined_context = self._combine_contexts(
            graph_result.context,
            dense_result.context
        )
        
        logger.info(f"Combined context length: {len(combined_context)} chars")
        
        # Merge metadata
        combined_metadata = {
            "retriever": self.get_name(),
            "execution_time": elapsed_time,
            "graph_metadata": graph_result.metadata,
            "dense_metadata": dense_result.metadata,
            "combine_strategy": self.combine_strategy,
            # Add context lengths for debugging
            "graph_context_length": len(graph_result.context),
            "dense_context_length": len(dense_result.context),
        }
        
        logger.info(f"Hybrid retrieval completed in {elapsed_time:.2f}s")
        
        return RetrievalResult(
            context=combined_context,
            metadata=combined_metadata
        )
    
    def _combine_contexts(self, graph_context: str, dense_context: str) -> str:
        """
        Combine contexts from both retrievers
        
        Args:
            graph_context: Context from graph retrieval
            dense_context: Context from dense retrieval
        
        Returns:
            Combined context string
        """
        if self.combine_strategy == "concatenate":
            # Simple concatenation with headers
            parts = []
            
            if graph_context:
                parts.append("=== Knowledge Graph Context ===")
                parts.append(graph_context)
            
            if dense_context:
                parts.append("\n=== Dense Retrieval Context ===")
                parts.append(dense_context)
            
            return "\n".join(parts) if parts else ""
        
        elif self.combine_strategy == "weighted":
            # Weighted combination (can be enhanced with actual weights)
            parts = []
            
            if graph_context:
                parts.append("=== Primary Knowledge (Graph) ===")
                parts.append(graph_context)
            
            if dense_context:
                parts.append("\n=== Supporting Knowledge (Dense) ===")
                parts.append(dense_context)
            
            return "\n".join(parts) if parts else ""
        
        else:
            # Default: just concatenate
            return f"{graph_context}\n\n{dense_context}".strip()
    
    def get_name(self) -> str:
        """Return retrieval name"""
        return "HybridRetrieval"


# Global instance for easy import
hybrid_retrieval = HybridRetrieval()
