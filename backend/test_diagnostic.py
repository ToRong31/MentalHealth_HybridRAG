"""
Test diagnostic retrieval to debug issue
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test Milvus connection and retrieval
from src.rag.vectors.dense_retriever import DenseRetriever

def test_diagnostic_retrieval():
    logger.info("Testing diagnostic retrieval...")
    
    try:
        # Initialize retriever
        retriever = DenseRetriever(collection_name="mental_health_diagnostic_support")
        
        # Test query
        query = "Tôi cảm thấy buồn chán và mất ngủ"
        logger.info(f"Query: {query}")
        
        # Retrieve
        results = retriever.retrieve([query], top_k=5)
        
        logger.info(f"Number of results: {len(results)}")
        logger.info(f"Results for first query: {len(results[0]) if results else 0}")
        
        if results and results[0]:
            for i, result in enumerate(results[0]):
                logger.info(f"Result {i+1}: {result}")
                
                # Try to get text
                if len(result) >= 1:
                    node_id = result[0]
                    text = retriever.get_dense_context_by_id(node_id)
                    logger.info(f"  Text (first 100 chars): {text[:100]}")
        else:
            logger.warning("No results returned!")
            
            # Check collection
            col = retriever.col
            logger.info(f"Collection name: {col.name}")
            logger.info(f"Collection count: {col.num_entities}")
            
            # Check schema
            logger.info(f"Collection schema: {col.schema}")
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    test_diagnostic_retrieval()
