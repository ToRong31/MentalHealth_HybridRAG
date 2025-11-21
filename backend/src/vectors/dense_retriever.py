from typing import List, Tuple
from pymilvus import connections, Collection

from src.config import MILVUS_DB, MILVUS_URI, MILVUS_TOKEN, E5_MODEL_NAME

from src.vectors.embeddings import encode_e5    
from src.vectors.embeddings import device  # hoặc import device từ nơi bạn định nghĩa
MILVUS_COLLECTION_NAME = "chat_16k"
class DenseRetriever:
    def __init__(self, collection_name: str | None = None):
        self.model_name = E5_MODEL_NAME
        self.device = device

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
