import sys
from pathlib import Path

# Add project root to path
# __file__ = /app/src/rag/ingestion/vectors/index.py
# Need to go up 5 levels to /app
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))
print(f"Project root: {project_root}")
print(f"Python path: {sys.path[0]}")

# backend/src/ingestion/vectors/index.py
import argparse
import json
import torch
import logging
from typing import Iterable, List, Tuple

import numpy as np
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from src.rag.config import rag_settings
from src.rag.vectors.embeddings import encode_e5


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

DEFAULT_COLLECTION = "mental_health_diagnostic_support"
EMBEDDING_DIM = 1024
DEFAULT_BATCH = 32
DEFAULT_INPUT = Path("data/raw/mental_health_diagnostic_support.jsonl")
DEFAULT_SKIP_FILE = Path("data/processed/mental_health_diagnostic_support_ids_embedded.txt")

# Collection configurations
COLLECTION_CONFIGS = {
    "mental_health_diagnostic_support": {
        "default_input": Path("data/raw/mental_health_diagnostic_support.jsonl"),
        "default_skip_file": Path("data/processed/mental_health_diagnostic_support_ids_embedded.txt"),
        "text_field": "text",
        "id_field": "chunk_id",
        "disease_field": "title",
        "is_jsonl": True,
        "has_disease_field": True,
    },
    "mental_health_treatment_guidance": {
        "default_input": Path("data/raw/mental_health_treatment_guidance.jsonl"),
        "default_skip_file": Path("data/processed/mental_health_treatment_guidance_ids_embedded.txt"),
        "text_field": "text",
        "id_field": "chunk_id",
        "disease_field": "title",
        "is_jsonl": True,
        "has_disease_field": True,
    },
}


def connect():
    if not rag_settings.MILVUS_URI:
        raise RuntimeError("Set MILVUS_URI in env before running")
    
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
    
    connections.connect(**connection_params)
    logger.info("Connected to Milvus")


def ensure_collection(name: str, dim: int, has_disease_field: bool = False) -> Collection:
    if name not in utility.list_collections():
        logger.info("Creating collection %s", name)
        fields = [
            FieldSchema(
                name="node_id",
                dtype=DataType.INT64,
                is_primary=True,
                auto_id=False,
                description="Item id",
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=dim,
                description="E5 embedding",
            ),
        ]
        
        # Add disease field if needed
        if has_disease_field:
            fields.append(
                FieldSchema(
                    name="disease",
                    dtype=DataType.VARCHAR,
                    max_length=500,
                    description="Disease or title field",
                )
            )
        
        schema = CollectionSchema(fields, description=f"{name} embeddings")
        col = Collection(name, schema)
        col.create_index(
            field_name="embedding",
            index_params={
                "index_type": "HNSW",
                "metric_type": "COSINE",
                "params": {"M": 16, "efConstruction": 200},
            },
        )
    else:
        col = Collection(name)
    col.load()
    return col


def load_skip_ids(path: Path | None) -> set[int]:
    if path is None:
        return set()
    if not path.exists():
        logger.info("Skip file %s not found; no IDs will be skipped", path)
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ids.add(int(line))
        except ValueError:
            logger.warning("Ignoring non-integer skip ID: %s", line)
    logger.info("Loaded %d IDs to skip from %s", len(ids), path)
    return ids


def iter_records(
    path: Path, 
    limit: int | None, 
    skip_ids: set[int],
    text_field: str = "answer",
    id_field: str = "id",
    is_jsonl: bool = False,
    disease_field: str | None = None
) -> Iterable[Tuple[int, str, str | None]]:
    """
    Iterate over records from input file.
    
    Args:
        path: Path to input file (JSON or JSONL)
        limit: Optional limit on number of records
        skip_ids: Set of IDs to skip
        text_field: Name of field containing text to embed
        id_field: Name of field containing the ID
        is_jsonl: True if file is JSONL format, False if JSON array
        disease_field: Optional name of field containing disease/title
    """
    if is_jsonl:
        # Read JSONL format (one JSON object per line)
        idx = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if limit is not None and idx >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                node_id = int(item[id_field])
                if node_id in skip_ids:
                    continue
                text = (item.get(text_field) or "").strip()
                disease = (item.get(disease_field) or "").strip() if disease_field else None
                # E5 passage prefix
                yield node_id, f"passage: {text}" if text else f"passage: id {node_id}", disease
                idx += 1
    else:
        # Read JSON array format
        data = json.loads(path.read_text(encoding="utf-8"))
        for idx, item in enumerate(data):
            if limit is not None and idx >= limit:
                break
            node_id = int(item[id_field])
            if node_id in skip_ids:
                continue
            text = (item.get(text_field) or "").strip()
            disease = (item.get(disease_field) or "").strip() if disease_field else None
            # E5 passage prefix
            yield node_id, f"passage: {text}" if text else f"passage: id {node_id}", disease


def append_embedded_ids(ids: List[int], path: Path | None):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for node_id in ids:
            f.write(f"{node_id}\n")


def insert_batches(
    col: Collection, records: Iterable[Tuple[int, str, str | None]], batch_size: int, skip_ids_path: Path | None, has_disease_field: bool = False
):
    ids: List[int] = []
    texts: List[str] = []
    diseases: List[str] = []
    total = 0
    for node_id, text, disease in records:
        ids.append(node_id)
        texts.append(text)
        if has_disease_field:
            diseases.append(disease or "")
        if len(ids) >= batch_size:
            embeddings = encode_e5(texts)
            if has_disease_field:
                col.insert([ids, embeddings.tolist(), diseases])
            else:
                col.insert([ids, embeddings.tolist()])
            append_embedded_ids(ids, skip_ids_path)
            total += len(ids)
            logger.info("Inserted %d rows", total)
            ids.clear()
            texts.clear()
            diseases.clear()
    if ids:
        embeddings = encode_e5(texts)
        if has_disease_field:
            col.insert([ids, embeddings.tolist(), diseases])
        else:
            col.insert([ids, embeddings.tolist()])
        append_embedded_ids(ids, skip_ids_path)
        total += len(ids)
        logger.info("Inserted %d rows", total)
    col.flush()
    logger.info("Flush complete; collection now has %d entities", col.num_entities)


def process_collection(collection_name: str, args, connect_first: bool = False):
    """Process a single collection"""
    # Get collection config
    if collection_name not in COLLECTION_CONFIGS:
        logger.warning("Unknown collection %s, using default settings", collection_name)
        config = {
            "default_input": Path(f"data/raw/{collection_name}.jsonl"),
            "default_skip_file": Path(f"data/processed/{collection_name}_ids_embedded.txt"),
            "text_field": "text",
            "id_field": "chunk_id",
            "is_jsonl": True,
            "has_disease_field": False,
        }
    else:
        config = COLLECTION_CONFIGS[collection_name]

    # Use config defaults if not specified
    input_path = args.input if args.input else config["default_input"]
    skip_ids_file = args.skip_ids_file if args.skip_ids_file else config["default_skip_file"]

    logger.info("=" * 60)
    logger.info("Collection: %s", collection_name)
    logger.info("Input file: %s", input_path)
    logger.info("Skip IDs file: %s", skip_ids_file)
    logger.info("Text field: %s, ID field: %s, JSONL: %s", 
                config["text_field"], config["id_field"], config["is_jsonl"])
    if config.get("has_disease_field"):
        logger.info("Disease field: %s", config.get("disease_field"))
    logger.info("=" * 60)

    if connect_first:
        connect()

    if args.drop and collection_name in utility.list_collections():
        logger.warning("Dropping existing collection %s", collection_name)
        utility.drop_collection(collection_name)

    col = ensure_collection(collection_name, EMBEDDING_DIM, config.get("has_disease_field", False))
    skip_ids = load_skip_ids(skip_ids_file)
    records = iter_records(
        input_path, 
        args.limit, 
        skip_ids,
        text_field=config["text_field"],
        id_field=config["id_field"],
        is_jsonl=config["is_jsonl"],
        disease_field=config.get("disease_field")
    )
    insert_batches(col, records, args.batch, skip_ids_file, config.get("has_disease_field", False))
    logger.info("✅ Completed collection: %s\n", collection_name)


def main():
    parser = argparse.ArgumentParser(description="Embed mental health data into Milvus")
    parser.add_argument("--input", type=Path, default=None, help="Path to input file (JSON or JSONL)")
    parser.add_argument("--collection", default=None, help="Milvus collection name (if not specified, process all)")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="Batch size for embedding")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing")
    parser.add_argument(
        "--skip-ids-file",
        type=Path,
        default=None,
        help="Path to file containing one ID per line to skip",
    )
    parser.add_argument("--drop", action="store_true", help="Drop collection before inserting")
    args = parser.parse_args()

    connect()

    # If no collection specified, process all collections
    if args.collection is None:
        logger.info("🚀 No collection specified - processing all collections")
        for collection_name in COLLECTION_CONFIGS.keys():
            process_collection(collection_name, args, connect_first=False)
        logger.info("🎉 All collections processed successfully!")
    else:
        # Process single collection
        process_collection(args.collection, args, connect_first=False)


if __name__ == "__main__":
    main()
