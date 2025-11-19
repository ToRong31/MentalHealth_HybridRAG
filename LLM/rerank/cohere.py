import cohere
import os
from typing import List, Dict, Any
os.environ["COHERE_API_KEY"] = "krQLb8VYg75J7dSUoOwENXz5YLgMHOYlwSqdV1H4"  # Replace with your actual Cohere API key
class CohereReranker:
    """
    Cohere Reranker class for document reranking
    """
    def __init__(self, api_key: str = None, model: str = "rerank-english-v3.0"):
        """
        Initialize Cohere Reranker
        
        Args:
            api_key: Cohere API key (if None, reads from COHERE_API_KEY env)
            model: Cohere rerank model to use
        """
        self.api_key = api_key or os.environ.get("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("COHERE_API_KEY not found in environment or constructor")
        
        self.model = model
        self.client = cohere.Client(self.api_key)
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using Cohere API
        
        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return
        
        Returns:
            List of dicts with keys: index, text, relevance_score
        """
        if not documents:
            return []
        
        try:
            results = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=True
            )
            
            reranked = []
            for result in results.results:
                reranked.append({
                    "index": result.index,
                    "text": result.document.text if hasattr(result.document, 'text') else documents[result.index],
                    "relevance_score": result.relevance_score
                })
            
            return reranked
        
        except Exception as e:
            print(f"[ERROR] Cohere rerank failed: {e}")
            return []
    
    def rerank_with_metadata(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        text_key: str = "text",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents with metadata preservation
        
        Args:
            query: Search query
            documents: List of document dicts (must have text_key)
            text_key: Key to extract text from document dict
            top_k: Number of top results to return
        
        Returns:
            List of original documents with added relevance_score, sorted by score
        """
        if not documents:
            return []
        
        try:
            # Extract texts for reranking
            texts = [doc.get(text_key, "") for doc in documents]
            
            # Call Cohere rerank
            results = self.client.rerank(
                model=self.model,
                query=query,
                documents=texts,
                top_n=top_k,
                return_documents=False
            )
            
            # Add scores to original documents
            reranked = []
            for result in results.results:
                doc = documents[result.index].copy()
                doc["cohere_score"] = result.relevance_score
                reranked.append(doc)
            
            return reranked
        
        except Exception as e:
            print(f"[ERROR] Cohere rerank with metadata failed: {e}")
            return []
    
    def rerank_anchors(
        self,
        query: str,
        anchor_data: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        Rerank anchor nodes from knowledge graph
        
        Args:
            query: User query
            anchor_data: List of dicts with keys: node_id, name, score
            top_k: Number of top results to keep
        
        Returns:
            List of reranked anchor dicts with added cohere_score
        """
        if not anchor_data:
            return []
        
        try:
            # Prepare documents (use node names)
            documents = [item.get("name", f"Node_{item.get('node_id', '')}") for item in anchor_data]
            
            # Call Cohere rerank
            results = self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_k,
                return_documents=False
            )
            
            # Map scores back to original data
            reranked = []
            for result in results.results:
                original_item = anchor_data[result.index].copy()
                original_item["cohere_score"] = result.relevance_score
                original_item["original_milvus_score"] = original_item.pop("score", 0.0)
                reranked.append(original_item)
            
            return reranked
        
        except Exception as e:
            print(f"[WARN] Cohere rerank anchors failed: {e}, using original order")
            return anchor_data[:top_k]


