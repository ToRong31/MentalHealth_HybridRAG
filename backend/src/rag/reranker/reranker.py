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
    
    def __init__(self, model: str = "rerank-english-v3.0"):
        """
        Initialize Cohere Reranker
        
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
        
        # If no API key, fallback to mock reranking
        if not self.client:
            return self._mock_rerank(candidates, top_k)
        
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
            print(f"⚠️  Cohere Rerank API error: {e}")
            print("   Falling back to mock reranking...")
            return self._mock_rerank(candidates, top_k)
    
    def _mock_rerank(
        self, 
        candidates: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback mock reranking (sort by Milvus score)
        
        Args:
            candidates: List of candidates
            top_k: Number of top results
        
        Returns:
            Top K candidates sorted by Milvus score
        """
        ranked = sorted(
            candidates,
            key=lambda x: x.get("original_milvus_score", 0.0),
            reverse=True,
        )
        
        # Copy Milvus score as Cohere score
        for c in ranked:
            c["cohere_score"] = float(c.get("original_milvus_score", 0.0))
        
        return ranked[:top_k]


# Global instance
reranker = CohereReranker()
