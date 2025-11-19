# Knowledge Graph Ingestion Module

Hệ thống ingestion đầy đủ để xây dựng knowledge graph từ dữ liệu text, bao gồm:
1. **LLM Extraction**: Trích xuất nodes và edges sử dụng Google Generative AI
2. **Neo4j Import**: Import graph vào Neo4j database
3. **Milvus Embedding**: Tạo embeddings và lưu vào Milvus vector database

## Cấu trúc Module

```
kg_therapist/ingestion/graph/
├── models.py              # Data models (Config, GraphData, Node, Edge)
├── llm_extractor.py       # LLM-based knowledge graph extractor
├── api_key_manager.py     # API key rotation and management
├── neo4j_writer.py        # Neo4j graph database writer
├── milvus_embedder.py     # Milvus vector database embedder
├── pipeline.py            # Main orchestration pipeline
├── promts/
│   └── graph_extraction_prompt.yaml  # Prompt template
└── __init__.py
```

## Cài đặt Dependencies

```bash
pip install langchain-google-genai
pip install neo4j
pip install pymilvus
pip install transformers torch
pip install pyyaml
```

## Cấu hình

### 1. Input Data
- **Input JSON**: `data/raw/input.json`
- Format: `[{"id": 1, "answer": "text..."}, ...]`

### 2. API Keys
- File: `data/raw/api_key.txt`
- Mỗi key một dòng

### 3. Neo4j
- URI: `bolt://localhost:7687`
- Username: `neo4j`
- Password: cần config

### 4. Milvus
- Local: `http://localhost:19530`
- Cloud (Zilliz): cần URI và token

## Sử dụng

### Chạy Full Pipeline

```bash
# Chạy toàn bộ: Extract → Neo4j → Milvus
python run_ingestion_pipeline.py --full \
    --neo4j-password YOUR_PASSWORD \
    --milvus-uri YOUR_MILVUS_URI \
    --milvus-token YOUR_TOKEN
```

### Chạy Từng Phase

```bash
# Phase 1: Extract knowledge graph
python run_ingestion_pipeline.py --extract --index 1-100

# Phase 2: Import to Neo4j
python run_ingestion_pipeline.py --neo4j \
    --neo4j-password YOUR_PASSWORD \
    --clear-neo4j

# Phase 3: Create embeddings
python run_ingestion_pipeline.py --embed \
    --milvus-uri YOUR_MILVUS_URI \
    --recreate-milvus
```

### Sử dụng Trong Code

```python
from kg_therapist.ingestion.graph import (
    Config,
    create_pipeline,
    load_api_keys_from_file
)

# Load API keys
api_keys = load_api_keys_from_file('data/raw/api_key.txt')

# Create config
config = Config(
    batch_size=5,
    model_name='gemini-2.0-flash-exp'
)

# Create pipeline
pipeline = create_pipeline(
    api_keys=api_keys,
    config=config,
    neo4j_password='your_password',
    milvus_uri='your_milvus_uri'
)

# Run full pipeline
success = pipeline.run_full_pipeline(
    index_filter='1-100',
    clear_neo4j=True,
    recreate_milvus=True
)
```

## Output Files

Sau khi chạy extraction, các file sau sẽ được tạo trong `data/processed/`:

- `nodes.csv`: Danh sách nodes (id, name, label)
- `edges.csv`: Danh sách edges (start_id, end_id, type, source_id)
- `processed_id.txt`: IDs đã xử lý thành công
- `errors_id.txt`: IDs gặp lỗi cần retry

## Components Chi Tiết

### 1. GraphExtractor (llm_extractor.py)

```python
from kg_therapist.ingestion.graph import GraphExtractor, Config, APIKeyManager

extractor = GraphExtractor(config, api_manager)
extractor.load_processed_and_errors()
success = extractor.extract_from_batch(batch, batch_num, total_batches)
```

**Features:**
- Batch processing với retry logic
- Node deduplication (O(1) lookup)
- Self-loop detection
- Progress tracking

### 2. Neo4jWriter (neo4j_writer.py)

```python
from kg_therapist.ingestion.graph import Neo4jWriter, Config

writer = Neo4jWriter(
    config=config,
    neo4j_uri='bolt://localhost:7687',
    neo4j_user='neo4j',
    neo4j_password='password'
)
success = writer.run(clear_existing=True)
```

**Features:**
- APOC support (dynamic labels/relationships)
- Pure Cypher fallback
- Batch import (10,000 items/batch)
- Automatic constraints creation
- Statistics reporting

### 3. MilvusEmbedder (milvus_embedder.py)

```python
from kg_therapist.ingestion.graph import MilvusEmbedder, Config

embedder = MilvusEmbedder(
    config=config,
    milvus_uri='http://localhost:19530',
    collection_name='kg_entities'
)
success = embedder.run(recreate_collection=True)
```

**Features:**
- E5-large-v2 embeddings (1024 dim)
- GPU support
- HNSW index với COSINE metric
- Batch processing
- Cloud Milvus (Zilliz) support

### 4. IngestionPipeline (pipeline.py)

Orchestrates toàn bộ quá trình:

```python
from kg_therapist.ingestion.graph import create_pipeline

pipeline = create_pipeline(api_keys=keys, ...)
pipeline.run_full_pipeline()
```

## Advanced Usage

### Custom Config

```python
config = Config(
    batch_size=10,
    max_retries=5,
    model_name='gemini-2.5-flash-lite',
    temperature=0.0,
    batch_delay=20.0
)
```

### API Key Range Selection

```bash
# Chỉ dùng keys 1-10
python run_ingestion_pipeline.py --full --api-keys 1-10

# Dùng specific keys
python run_ingestion_pipeline.py --full --api-keys 1,5,10,15
```

### Index Filtering

```bash
# Chỉ xử lý items 1-100
python run_ingestion_pipeline.py --extract --index 1-100

# Xử lý specific items
python run_ingestion_pipeline.py --extract --index 1,10,50,100
```

## Monitoring

### Logs

- Console output: Real-time progress
- File: `ingestion_pipeline.log`

### Progress Files

```bash
# Xem số lượng đã xử lý
wc -l data/processed/processed_id.txt

# Xem errors
cat data/processed/errors_id.txt
```

### Neo4j Stats

```cypher
// Total nodes
MATCH (n) RETURN count(n)

// Node labels distribution
MATCH (n)
UNWIND labels(n) AS label
RETURN label, count(*) AS count
ORDER BY count DESC

// Relationship types
MATCH ()-[r]->()
RETURN type(r), count(*) AS count
ORDER BY count DESC
```

### Milvus Stats

```python
from pymilvus import Collection

collection = Collection("kg_entities")
collection.load()
print(f"Total entities: {collection.num_entities}")
```

## Troubleshooting

### API Rate Limits

```python
config = Config(
    min_delay_between_calls=10.0,  # Tăng delay
    batch_delay=30.0,              # Tăng delay giữa batches
    rate_limit_delay=120.0         # Tăng delay khi hit 429
)
```

### Memory Issues

- Giảm `batch_size` trong Config
- Giảm `batch_size` trong Neo4jWriter/MilvusEmbedder

### Neo4j Connection

```bash
# Kiểm tra Neo4j đang chạy
docker ps | grep neo4j

# Test connection
cypher-shell -u neo4j -p password
```

### Milvus Connection

```bash
# Local Milvus
docker ps | grep milvus

# Test connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530')"
```

## Best Practices

1. **Incremental Processing**: Pipeline tự động skip processed IDs
2. **Error Recovery**: Failed IDs được lưu để retry
3. **Batch Size**: Start nhỏ (5), scale lên khi stable
4. **API Keys**: Rotate nhiều keys để tránh rate limits
5. **Monitoring**: Xem logs và stats thường xuyên

## Examples

Xem thêm trong `run_ingestion_pipeline.py` để có examples chi tiết về cách sử dụng.

