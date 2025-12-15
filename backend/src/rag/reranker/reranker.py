import os
from typing import List, Dict, Any
import cohere
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class CohereReranker:
    """
    Cohere Reranker using rerank-english-v3.0 model
    """
    
    def __init__(self, model: str = "rerank-v4.0-fast"):
        """
        Initialize Cohere RerankerR
        
        Args:
            model: Cohere rerank model name
        """
        self.api_key = os.getenv("COHERE_API_KEY")
        if not self.api_key or self.api_key == "your_cohere_api_key_here":
            print("⚠️  WARNING: COHERE_API_KEY not set. Using mock reranking (sorting by Milvus score).")
            self.client = None
        else:
            self.client = cohere.Client(self.api_key)
        
        self.model = model
    
    def rerank_anchors(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using Cohere Rerank API
        
        Args:
            query: User query
            candidates: List of candidate dicts with 'node_id', 'name', 'original_milvus_score'
            top_k: Number of top results to return
        
        Returns:
            Reranked candidates with 'cohere_score' added
        """
        if not candidates:
            return []
        
        # Check if API key is available
        if not self.client:
            raise RuntimeError("COHERE_API_KEY not set. Cannot perform reranking without API key.")
        
        try:
            # Prepare documents for Cohere (use node names as documents)
            documents = [c.get("name", f"Node_{c['node_id']}") for c in candidates]
            
            # Call Cohere Rerank API
            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=False
            )
            
            # Map results back to candidates
            reranked = []
            for result in response.results:
                idx = result.index
                score = result.relevance_score
                
                # Get original candidate
                candidate = candidates[idx].copy()
                candidate["cohere_score"] = float(score)
                reranked.append(candidate)
            
            return reranked
            
        except Exception as e:
            print(f"❌ Cohere Rerank API error: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Cohere rerank_anchors failed: {e}") from e
    
    def rerank_chunks(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank text chunks using Cohere Rerank API
        Specifically designed for dense retrieval chunks with full text content
        
        Args:
            query: User query
            candidates: List of candidate dicts with 'chunk_id', 'text', 'original_milvus_score'
            top_k: Number of top results to return
        
        Returns:
            Reranked candidates with 'cohere_score' added
        """
        if not candidates:
            return []
        
        # Check if API key is available
        if not self.client:
            raise RuntimeError("COHERE_API_KEY not set. Cannot perform reranking without API key.")
        
        try:
            # Prepare documents for Cohere (use full text content)
            documents = []
            for c in candidates:
                # Get text content from 'text' or 'content' field
                text = c.get("text") or c.get("content", "")
                if not text:
                    chunk_id = c.get('chunk_id')
                    print(f"⚠️  Warning: No text content for chunk {chunk_id}")
                    text = f"Chunk_{chunk_id}"
                documents.append(text)
            
            # Call Cohere Rerank API
            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=False
            )
            
            # Map results back to candidates
            reranked = []
            for result in response.results:
                idx = result.index
                score = result.relevance_score
                
                # Get original candidate
                candidate = candidates[idx].copy()
                candidate["cohere_score"] = float(score)
                reranked.append(candidate)
            
            return reranked
            
        except Exception as e:
            print(f"❌ Cohere Rerank API error: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Cohere rerank_chunks failed: {e}") from e
    


# Global instance
reranker = CohereReranker()
