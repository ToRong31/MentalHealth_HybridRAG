# backend/src/ingestion/vectors/index.py
import argparse
import json
import torch
import logging
from pathlib import Path
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

from src.rag.config import MILVUS_DB, MILVUS_TOKEN, MILVUS_URI
from src.rag.vectors.embeddings import encode_e5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

DEFAULT_COLLECTION = "chat_16k"
EMBEDDING_DIM = 1024
DEFAULT_BATCH = 32
DEFAULT_INPUT = Path("data/raw/input.json")
DEFAULT_SKIP_FILE = Path("data/processed/embedded_chat_ids.txt")


def connect():
    if not MILVUS_URI or not MILVUS_TOKEN:
        raise RuntimeError("Set MILVUS_URI and MILVUS_TOKEN in env before running")
    connections.connect(
        alias="default",
        uri=MILVUS_URI,
        token=MILVUS_TOKEN,
        secure=True,
        db_name=MILVUS_DB,
    )
    logger.info("Connected to Milvus")


def ensure_collection(name: str, dim: int) -> Collection:
    if name not in utility.list_collections():
        logger.info("Creating collection %s", name)
        schema = CollectionSchema(
            [
                FieldSchema(
                    name="node_id",
                    dtype=DataType.INT64,
                    is_primary=True,
                    auto_id=False,
                    description="Chat item id",
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=dim,
                    description="E5 embedding",
                ),
            ],
            description="chat_16k embeddings",
        )
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


def iter_records(path: Path, limit: int | None, skip_ids: set[int]) -> Iterable[Tuple[int, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    for idx, item in enumerate(data):
        if limit is not None and idx >= limit:
            break
        node_id = int(item["id"])
        if node_id in skip_ids:
            continue
        text = (item.get("answer") or "").strip()
        # E5 passage prefix
        yield node_id, f"passage: {text}" if text else f"passage: id {node_id}"


def append_embedded_ids(ids: List[int], path: Path | None):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for node_id in ids:
            f.write(f"{node_id}\n")


def insert_batches(
    col: Collection, records: Iterable[Tuple[int, str]], batch_size: int, skip_ids_path: Path | None
):
    ids: List[int] = []
    texts: List[str] = []
    total = 0
    for node_id, text in records:
        ids.append(node_id)
        texts.append(text)
        if len(ids) >= batch_size:
            embeddings = encode_e5(texts)
            col.insert([ids, embeddings.tolist()])
            append_embedded_ids(ids, skip_ids_path)
            total += len(ids)
            logger.info("Inserted %d rows", total)
            ids.clear()
            texts.clear()
    if ids:
        embeddings = encode_e5(texts)
        col.insert([ids, embeddings.tolist()])
        append_embedded_ids(ids, skip_ids_path)
        total += len(ids)
        logger.info("Inserted %d rows", total)
    col.flush()
    logger.info("Flush complete; collection now has %d entities", col.num_entities)


def main():
    parser = argparse.ArgumentParser(description="Embed chat_16k answers into Milvus")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to input.json")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="Milvus collection name")
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="Batch size for embedding")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing")
    parser.add_argument(
        "--skip-ids-file",
        type=Path,
        default=DEFAULT_SKIP_FILE,
        help="Path to file containing one ID per line to skip (default: data/processed/embedded_chat_ids.txt)",
    )
    parser.add_argument("--drop", action="store_true", help="Drop collection before inserting")
    args = parser.parse_args()

    connect()

    if args.drop and args.collection in utility.list_collections():
        logger.warning("Dropping existing collection %s", args.collection)
        utility.drop_collection(args.collection)

    col = ensure_collection(args.collection, EMBEDDING_DIM)
    skip_ids = load_skip_ids(args.skip_ids_file)
    records = iter_records(args.input, args.limit, skip_ids)
    insert_batches(col, records, args.batch, args.skip_ids_file)


if __name__ == "__main__":
    main()
