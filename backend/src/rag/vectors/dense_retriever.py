from typing import List, Tuple
from pymilvus import connections, Collection

from src.rag.config import MILVUS_DB, MILVUS_URI, MILVUS_TOKEN, E5_MODEL_NAME

from src.rag.vectors.embeddings import encode_e5    
from src.rag.vectors.embeddings import device  # hoặc import device từ nơi bạn định nghĩa
import json

MILVUS_COLLECTION_NAME = "chat_16k"
class DenseRetriever:
    def __init__(self, collection_name: str | None = None):
        self.model_name = E5_MODEL_NAME
        self.device = device
        self.path_context="data/raw/input.json"

        # Kết nối Milvus/Zilliz
        connections.connect(
            alias="default",
            uri=MILVUS_URI,
            token=MILVUS_TOKEN,
            secure=True,
            db_name=MILVUS_DB,
        )

        self.collection_name = collection_name or MILVUS_COLLECTION_NAME
        self.col = Collection(self.collection_name)
        self.col.load()

        # Tham số search (phù hợp index HNSW COSINE trong index.py)
        self.search_params = {
            "metric_type": "COSINE",
            "params": {"ef": 64},  # tùy chỉnh được
        }

    def retrieve(self, queries: List[str], top_k: int = 5) -> List[List[Tuple[int, float]]]:
        """
        Trả về list kết quả cho mỗi query:
        [
          [(node_id1, score1), (node_id2, score2), ...],  # cho query 1
          [(...), ...],                                   # cho query 2
          ...
        ]
        """
        # Encode queries thành embeddings
        encoded_queries = [f"query: {q}" for q in queries]
        query_embeddings = encode_e5(encoded_queries)  # shape: (len(queries), 1024)

        # Milvus cần list[list[float]]
        query_vectors = query_embeddings.tolist()

        # Search trong Milvus
        search_results = self.col.search(
            data=query_vectors,
            anns_field="embedding",       # tên field vector
            param=self.search_params,
            limit=top_k,
            output_fields=["node_id"],
        )

        all_results: List[List[Tuple[int, float]]] = []
        for hits in search_results:  # hits: list[Hit] cho từng query
            one_query_results: List[Tuple[int, float]] = []
            for hit in hits:
                # node_id được lấy từ field trong entity
                node_id = hit.entity.get("node_id")
                score = float(hit.score)
                one_query_results.append((node_id, score))
            all_results.append(one_query_results)

        return all_results

    def get_dense_context_by_id(self, node_id: int) -> str:
        """
        Lấy field 'answer' tương ứng với node_id truyền vào.

        Giả sử trong file JSON mỗi phần tử có dạng:
        {
            "id": <int>,
            "answer": "<chuỗi trả lời>",
            ...
        }
        """
        with open(self.path_context, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Tìm item có field 'id' trùng với node_id
        for item in data:
            if item.get("id") == node_id:
                return item.get("answer", "")

        # Không tìm thấy thì trả về chuỗi rỗng (tuỳ bạn muốn raise exception hay không)
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