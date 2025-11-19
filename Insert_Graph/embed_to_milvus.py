# embed_to_milvus_e5.py

from neo4j import GraphDatabase
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F
import numpy as np

# =============================
# CONFIG
# =============================
URI   = "bolt://127.0.0.1:7687"
AUTH  = ("neo4j", "torong31102005")

MODEL_NAME = "intfloat/e5-large-v2"
DIM        = 1024              # e5-large-v2
COLL       = "kg_entities"

# =============================
# CONNECT NEO4J
# =============================
driver = GraphDatabase.driver(URI, auth=AUTH)

# =============================
# LOAD HUGGINGFACE RAW E5 MODEL
# =============================
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Using device: {device}")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model     = AutoModel.from_pretrained(MODEL_NAME).to(device)
model.eval()


# =============================
# E5 POOLING FUNCTION
# =============================
def average_pool(last_hidden_states, attention_mask):
    last_hidden = last_hidden_states.masked_fill(
        ~attention_mask[..., None].bool(),
        0.0
    )
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]


# =============================
# E5 ENCODING FUNCTION
# =============================
def encode_e5(texts, batch_size=32):
    all_embs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]

            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(device)

            outputs = model(**inputs)
            pooled = average_pool(outputs.last_hidden_state, inputs["attention_mask"])
            pooled = F.normalize(pooled, p=2, dim=1)

            all_embs.append(pooled.cpu().numpy())

    return np.vstack(all_embs)     # shape [N, 1024]


# =============================
# CONNECT MILVUS / ZILLIZ
# =============================
connections.connect(
    alias="default",
    uri="https://in03-b3ec3bf1a4be5eb.serverless.aws-eu-central-1.cloud.zilliz.com",
    token="6ed108e8036c9eb92e50b9bff86e0ae657efda8c827ad090e493f601268132189250a4a907338420c87053d8d8fbc156af7e1b25",
    secure=True,
    db_name="default"
)

# =============================
# CREATE COLLECTION IF NEEDED
# =============================
if COLL not in utility.list_collections():
    fields = [
        FieldSchema(name="node_id",   dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields, description="KG entities embeddings (E5)")
    col = Collection(COLL, schema)

    col.create_index(
        field_name="embedding",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
else:
    col = Collection(COLL)

col.load()

# =============================
# READ NODES FROM NEO4J
# =============================
GET = """
MATCH (n:Entity)
WHERE n.id IS NOT NULL AND n.id >= 1
RETURN n.id AS id, n.name AS name, n.label AS label
ORDER BY n.id ASC
"""

pairs = []
with driver.session() as s:
    rows = list(s.run(GET))
    for r in rows:
        rid = int(r["id"])
        name = (r["name"] or "").strip()
        label = r["label"] or ""
        full = f"{name} [{label}]" if label else name
        if not full:
            full = f"node {rid}"

        # 🔥 prefix bắt buộc cho E5
        pairs.append((rid, f"passage: {full}"))

node_ids = [rid for rid, _ in pairs]
texts    = [txt for _, txt in pairs]

print(f"[INFO] Encoding {len(texts)} nodes...")

embs = encode_e5(texts)
assert embs.shape[1] == DIM

# =============================
# INSERT TO MILVUS
# =============================
BATCH = 1000
def chunk(x, n):
    for i in range(0, len(x), n):
        yield x[i:i+n]

for id_batch, vec_batch in zip(chunk(node_ids, BATCH), chunk(embs, BATCH)):
    col.insert([id_batch, vec_batch.tolist()])

print(f"✅ DONE: Inserted {len(node_ids)} embeddings into Milvus (E5)")
