# Ingestion Module Architecture

## 📐 Kiến trúc tổng thể

Module ingestion sử dụng **shared config và clients** từ `src` để đảm bảo consistency across toàn bộ hệ thống.

```
src/
├── config.py                    # 🔧 Centralized config
├── vectors/
│   ├── embeddings.py            # 🧠 Shared E5 model
│   └── milvus_client.py         # 📊 Shared Milvus client
├── graph/
│   └── neo4j_client.py          # 🗄️ Shared Neo4j client
└── ingestion/
    └── graph/
        ├── models.py            # 📦 Data models
        ├── llm_extractor.py     # 🔍 LLM extraction
        ├── milvus_embedder.py   # ➡️ Uses shared embeddings
        ├── neo4j_writer.py      # ➡️ Uses shared config
        └── pipeline.py          # 🎯 Orchestration
```

## 🔧 Centralized Configuration

**File**: `src/config.py`

```python
# E5 Model
E5_MODEL_NAME = "intfloat/e5-large-v2"

# Milvus / Zilliz Cloud
MILVUS_URI = "https://in03-xxx.cloud.zilliz.com"
MILVUS_TOKEN = "xxx"
MILVUS_DB = "default"
MILVUS_COLLECTION = "kg_entities"

# Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "torong31102005"

# Gemini
GEMINI_MODEL_NAME = "gemini-2.5-flash"
```

**Lợi ích**:
- ✅ Single source of truth
- ✅ Environment variables support
- ✅ Easy to override trong code
- ✅ Consistency across modules

## 🧠 Shared Embedding Model

**File**: `src/vectors/embeddings.py`

### Features:
- **Model**: E5-large-v2 (1024 dimensions)
- **Device**: Auto GPU/CPU detection
- **Singleton**: Model loaded once, shared across app
- **Format**: 
  - Queries: `"query: {text}"`
  - Documents: `"passage: {text}"`

### Usage in Ingestion:

```python
from src.vectors.embeddings import encode_e5

# Batch encoding
texts = ["passage: anxiety [SYMPTOM]", "passage: therapy [INTERVENTION]"]
embeddings = encode_e5(texts)  # (N, 1024) normalized numpy array
```

**Benefits**:
- ✅ No duplicate model loading
- ✅ Consistent embeddings across retrieval & ingestion
- ✅ Memory efficient
- ✅ Same preprocessing logic

## 📊 Shared Milvus Client

**File**: `src/vectors/milvus_client.py`

### Global Connection:
```python
from pymilvus import connections, Collection
from src.config import MILVUS_URI, MILVUS_TOKEN, MILVUS_COLLECTION

# Global connection setup
connections.connect(
    alias="default",
    uri=MILVUS_URI,
    token=MILVUS_TOKEN,
    secure=True,
    db_name=MILVUS_DB
)

# Global collection
col = Collection(MILVUS_COLLECTION)
col.load()
```

### Usage Pattern:
- **Ingestion**: Uses connection to create/insert data
- **Retrieval**: Uses `milvus_search()` for querying

## 🗄️ Shared Neo4j Client

**File**: `src/graph/neo4j_client.py`

### Global Driver:
```python
from neo4j import GraphDatabase
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

# Global driver
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
```

### Usage Pattern:
- **Ingestion**: Uses driver pattern for batch writes
- **Retrieval**: Uses `expand_subgraph()`, `get_node_names_from_neo4j()`

## 🔍 LLM Extractor

**File**: `src/ingestion/graph/llm_extractor.py`

### Responsibilities:
- Extract nodes/edges from text using LLM
- Batch processing with retry logic
- Node deduplication (O(1) lookup)
- Progress tracking
- Error recovery

### Does NOT use shared clients:
- Creates own LLM instances per batch (for API key rotation)
- Writes to CSV files directly

## ➡️ Milvus Embedder

**File**: `src/ingestion/graph/milvus_embedder.py`

### Uses Shared Resources:
```python
from src.config import MILVUS_URI, MILVUS_TOKEN, MILVUS_COLLECTION
from src.vectors.embeddings import encode_e5
```

### Architecture:
1. **Reads nodes** from CSV
2. **Creates embeddings** using `encode_e5()` (shared E5 model)
3. **Connects to Milvus** using config
4. **Creates collection** if not exists
5. **Inserts embeddings** in batches

### Key Methods:
```python
embedder = MilvusEmbedder(config, nodes_file="data/processed/nodes.csv")

# Uses shared E5 model
node_ids, embeddings = embedder.create_embeddings(nodes)

# Uses shared Milvus config
embedder.insert_embeddings(node_ids, embeddings)
```

## ➡️ Neo4j Writer

**File**: `src/ingestion/graph/neo4j_writer.py`

### Uses Shared Config:
```python
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
```

### Architecture:
1. **Reads nodes/edges** from CSV
2. **Connects to Neo4j** using config
3. **Checks APOC** availability
4. **Writes nodes** with dynamic labels
5. **Writes edges** with dynamic relationship types

### Key Methods:
```python
writer = Neo4jWriter(config, nodes_file="data/processed/nodes.csv")

# Uses shared Neo4j config
writer.write_nodes(nodes)
writer.write_edges(edges)
```

## 🎯 Pipeline Orchestration

**File**: `src/ingestion/graph/pipeline.py`

### Workflow:
```
1. Extract (LLM)     → CSV files (nodes.csv, edges.csv)
2. Import (Neo4j)    → Graph database
3. Embed (Milvus)    → Vector database
```

### Factory Pattern:
```python
from src.ingestion.graph import create_pipeline

pipeline = create_pipeline(
    api_keys=keys,
    # All config from src.config by default
    # Can override if needed
)

pipeline.run_full_pipeline()
```

## 🔄 Data Flow

```
Input JSON (data/raw/input.json)
    ↓
[LLM Extractor]
    ↓
CSV Files (data/processed/)
    ├── nodes.csv (id, name, label)
    └── edges.csv (start_id, end_id, type, source_id)
    ↓
[Neo4j Writer] → Neo4j Graph Database
    ↑             ↓
    └─────────────┘
    (Uses src.config)
    ↓
[Milvus Embedder] → Milvus Vector DB
    ↑
    └── Uses src.vectors.embeddings (shared E5)
```

## 📦 Module Exports

**File**: `src/ingestion/graph/__init__.py`

```python
from src.ingestion.graph import (
    # Models
    Config, GraphData, Node, Edge,
    
    # Components
    GraphExtractor,
    Neo4jWriter,
    MilvusEmbedder,
    
    # Pipeline
    IngestionPipeline,
    create_pipeline,
    
    # API Key Management
    APIKeyManager,
    load_api_keys_from_file,
    load_api_keys_by_lines
)
```

## 🚀 Usage Examples

### 1. Full Pipeline (Uses All Shared Resources)

```python
from src.ingestion.graph import create_pipeline, load_api_keys_from_file

# Load API keys
api_keys = load_api_keys_from_file('data/raw/api_key.txt')

# Create pipeline (uses src.config)
pipeline = create_pipeline(api_keys=api_keys)

# Run full pipeline
pipeline.run_full_pipeline(
    index_filter='1-100',
    clear_neo4j=True,
    recreate_milvus=True
)
```

### 2. Individual Phases

```python
# Extract only
pipeline.run_extraction(input_data)

# Neo4j import (uses shared config)
pipeline.run_neo4j_import(clear_existing=True)

# Milvus embedding (uses shared E5 model)
pipeline.run_embedding(recreate_collection=True)
```

### 3. CLI with Config Defaults

```bash
# Uses all defaults from src.config
python run_ingestion_pipeline.py --full

# Override specific configs
python run_ingestion_pipeline.py --full \
    --neo4j-password custom_password \
    --milvus-uri custom_uri
```

## ✅ Benefits of This Architecture

### 1. **Consistency**
- Same embeddings in ingestion & retrieval
- Same connection configs everywhere
- No drift between modules

### 2. **Maintainability**
- Single config file to update
- Shared code = less duplication
- Easy to understand data flow

### 3. **Performance**
- E5 model loaded once, shared
- Milvus connection reused
- Neo4j driver pooling

### 4. **Flexibility**
- Can override configs when needed
- Environment variables support
- Easy to test with mocks

### 5. **Scalability**
- Modular design
- Each phase can run independently
- Easy to add new phases

## 🔧 Configuration Override

If you need to override config for specific use cases:

```python
from src.ingestion.graph import create_pipeline

pipeline = create_pipeline(
    api_keys=keys,
    neo4j_uri="bolt://custom:7687",      # Override
    neo4j_user="custom_user",             # Override
    milvus_uri="http://custom:19530"      # Override
)
```

Default values from `src.config` are used if not specified.

## 📝 Notes

1. **E5 Model**: Singleton pattern, loaded once in `src.vectors.embeddings`
2. **Milvus Connection**: Global connection in `src.vectors.milvus_client`
3. **Neo4j Driver**: Global driver in `src.graph.neo4j_client`
4. **Config**: Centralized in `src.config` with env var support

This architecture ensures **consistency**, **maintainability**, and **performance** across the entire knowledge graph system! 🎉

