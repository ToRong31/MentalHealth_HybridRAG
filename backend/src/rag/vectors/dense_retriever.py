from typing import List, Tuple
from pymilvus import connections, Collection

from src.rag.config import rag_settings

from src.rag.vectors.embeddings import encode_e5    
from src.rag.vectors.embeddings import device
import json

MILVUS_COLLECTION_NAME = "mental_health_diagnostic_support"

# Mapping collection names to their data files
COLLECTION_DATA_FILES = {
    "mental_health_diagnostic_support": "data/raw/mental_health_diagnostic_support.jsonl",
    "mental_health_treatment_guidance": "data/raw/mental_health_treatment_guidance.jsonl",
    "normal_response": "data/raw/normal_responses.jsonl",
}

# Mapping collection names to their metadata field (disease/type/etc.)
COLLECTION_METADATA_FIELDS = {
    "mental_health_diagnostic_support": "disease",
    "mental_health_treatment_guidance": "disease",
    "normal_response": "type",
}

class DenseRetriever:
    def __init__(self, collection_name: str | None = None, context_file: str | None = None):
        self.model_name = rag_settings.E5_MODEL_NAME
        self.device = device
        
        # Determine collection name
        self.collection_name = collection_name or MILVUS_COLLECTION_NAME
        
        # Determine metadata field (disease, type, etc.)
        self.metadata_field = COLLECTION_METADATA_FIELDS.get(
            self.collection_name,
            "disease"  # fallback default
        )
        
        # Determine context file path
        if context_file:
            self.path_context = context_file
        else:
            # Use default mapping based on collection name
            self.path_context = COLLECTION_DATA_FILES.get(
                self.collection_name,
                "data/raw/mental_health_diagnostic_support.jsonl"  # fallback default
            )

        # Lazy loading - connection will be established when needed
        self._col = None
        self._connected = False
        
        # Tham số search (phù hợp index HNSW COSINE trong index.py)
        self.search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64},  # tùy chỉnh được
        }
    
    def _ensure_connection(self):
        """Ensure Milvus connection is established (lazy loading)"""
        if self._connected and self._col is not None:
            return
        
        # Connection parameters
        connection_params = {
            "alias": "default",
            "uri": rag_settings.MILVUS_URI,
            "db_name": rag_settings.MILVUS_DB,
        }
        
        # Only add token and secure for cloud deployment
        if rag_settings.MILVUS_TOKEN and rag_settings.MILVUS_TOKEN.strip():
            connection_params["token"] = rag_settings.MILVUS_TOKEN
            connection_params["secure"] = True
        else:
            connection_params["secure"] = False
        
        # Kết nối Milvus
        connections.connect(**connection_params)

        self._col = Collection(self.collection_name)
        self._col.load()
        self._connected = True
    
    @property
    def col(self):
        """Property to access collection with lazy loading"""
        self._ensure_connection()
        return self._col

    def retrieve(self, queries: List[str], top_k: int = 5) -> List[List[Tuple[int, float, str]]]:
        """
        Trả về list kết quả cho mỗi query:
        [
          [(node_id1, score1, metadata1), (node_id2, score2, metadata2), ...],  # cho query 1
          [(...), ...],                                   # cho query 2
          ...
        ]
        metadata có thể là disease, type, hoặc field khác tùy collection
        """
        # Encode queries thành embeddings
        encoded_queries = [f"query: {q}" for q in queries]
        query_embeddings = encode_e5(encoded_queries)  # shape: (len(queries), 1024)

        # Milvus cần list[list[float]]
        query_vectors = query_embeddings.tolist()

        # Search trong Milvus with dynamic metadata field
        search_results = self.col.search(
            data=query_vectors,
            anns_field="embedding",       # tên field vector
            param=self.search_params,
            limit=top_k,
            output_fields=["node_id", self.metadata_field],  # Dynamic field (disease/type)
        )

        all_results: List[List[Tuple[int, float, str]]] = []  # (node_id, score, metadata)
        for hits in search_results:  # hits: list[Hit] cho từng query
            one_query_results: List[Tuple[int, float, str]] = []
            for hit in hits:
                # node_id (primary key) và metadata field được lấy từ entity
                node_id = hit.entity.get("node_id")
                # Hit.entity.get() doesn't support default value, use try-except
                try:
                    metadata_value = hit.entity.get(self.metadata_field) or ""
                except:
                    metadata_value = ""
                score = float(hit.score)
                one_query_results.append((node_id, score, metadata_value))
            all_results.append(one_query_results)

        return all_results

    def get_dense_context_by_id(self, node_id: int) -> str:
        """
        Lấy nội dung văn bản tương ứng với node_id truyền vào.
        Hỗ trợ cả JSON và JSONL format.
        
        JSON format (chat_16k):
        {
            "id": <int>,
            "answer": "<chuỗi trả lời>",
            ...
        }
        
        JSONL format (clinicalbook):
        {
            "chunk_id": "<string>",
            "title": "<string>",
            "section_type": "<string>",
            "text": "<nội dung>"
        }
        """
        # Check if file is JSONL or JSON
        is_jsonl = self.path_context.endswith('.jsonl')
        
        if is_jsonl:
            # Read JSONL format (ClinicalBook)
            with open(self.path_context, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        # Try both string and int comparison for chunk_id
                        chunk_id = item.get("chunk_id")
                        if chunk_id is not None:
                            # Convert both to string for comparison
                            if str(chunk_id) == str(node_id):
                                # Build context from all fields
                                title = item.get("title", "")
                                section_type = item.get("section_type", "")
                                text = item.get("text", "")
                                
                                # Format: Title | Section Type: Text
                                if title and section_type:
                                    return f"{title} | {section_type}: {text}"
                                else:
                                    return text
        else:
            # Read JSON format (chat_16k)
            with open(self.path_context, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Tìm item có field 'id' trùng với node_id
            for item in data:
                if item.get("id") == node_id:
                    return item.get("answer", "")

        # Không tìm thấy thì trả về chuỗi rỗng
        return ""
    def build_dense_context(self, results: List[Tuple[int, float]]) -> str:
        """
        Xây dựng dense context từ kết quả retrieve.
        
        Args:
            results: List các tuple (node_id, score)
        
        Returns:
            Chuỗi context được nối từ các đoạn văn bản tương ứng với node_id
        """
        node_ids = [node_id for node_id, _ in results]
        contexts = [self.get_dense_context_by_id(node_id) for node_id in node_ids]
        dense_context = "\n".join(contexts)
        return dense_context
    
    def get_name_collection(self) -> str:
        return self.collection_name