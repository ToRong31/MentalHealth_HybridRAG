"""
Embeddings utilities for RAG retrieval.

Provides lazy-loaded sentence-transformers encoder with graceful fallback.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_model = None
_dim = 384


def _get_model() -> Any:
    """Lazy init embedding model."""
    global _model, _dim
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer

        model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        _model = SentenceTransformer(model_name)
        try:
            _dim = int(_model.get_sentence_embedding_dimension())
        except Exception:
            _dim = 384
        logger.info("[Embeddings] Loaded model %s (dim=%d)", model_name, _dim)
        return _model

    except Exception as e:
        logger.warning("[Embeddings] Model load failed, using hash fallback: %s", e)
        _model = False  # sentinel
        _dim = 384
        return _model


def _hash_fallback(text: str, dim: int = 384) -> list[float]:
    """Deterministic fallback embedding when model is unavailable."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vals = []
    for i in range(dim):
        b = digest[i % len(digest)]
        vals.append((b / 255.0) * 2.0 - 1.0)

    # L2 normalize
    import math

    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def encode_text(text: str) -> list[float]:
    """Encode single text into vector embedding."""
    model = _get_model()
    if model is False:
        return _hash_fallback(text, _dim)

    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)
    except Exception as e:
        logger.warning("[Embeddings] encode_text failed, fallback used: %s", e)
        return _hash_fallback(text, _dim)


def encode_batch(texts: list[str]) -> list[list[float]]:
    """Encode batch of texts."""
    model = _get_model()
    if model is False:
        return [_hash_fallback(t, _dim) for t in texts]

    try:
        vectors = model.encode(texts, normalize_embeddings=True)
        out = []
        for v in vectors:
            out.append(v.tolist() if hasattr(v, "tolist") else list(v))
        return out
    except Exception as e:
        logger.warning("[Embeddings] encode_batch failed, fallback used: %s", e)
        return [_hash_fallback(t, _dim) for t in texts]
