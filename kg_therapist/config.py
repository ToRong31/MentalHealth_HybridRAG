import os

# E5
E5_MODEL_NAME = "intfloat/e5-large-v2"

# Milvus / Zilliz
MILVUS_URI = "https://in03-b3ec3bf1a4be5eb.serverless.aws-eu-central-1.cloud.zilliz.com"
MILVUS_TOKEN = "6ed108e8036c9eb92e50b9bff86e0ae657efda8c827ad090e493f601268132189250a4a907338420c87053d8d8fbc156af7e1b25"
MILVUS_DB = os.getenv("MILVUS_DB", "default")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "kg_entities")

# Neo4j
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "torong31102005")

# Gemini
# Note: GEMINI_API_KEY không còn được sử dụng - giờ dùng API Key Manager với multiple keys
# GEMINI_API_KEY = "AIzaSyD634mILnnetcT5JsP-AMtyq7rF9B9Rr0c"
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
