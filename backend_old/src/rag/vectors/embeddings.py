from typing import List
import logging

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

from src.rag.config import rag_settings

logger = logging.getLogger(__name__)

# Device selection with detailed logging
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")


# ============================================================================
# SINGLETON MODEL LOADING - Loads ONCE when module is imported
# Model stays in memory (GPU/CPU) and is reused for ALL requests
# ============================================================================

tokenizer = AutoTokenizer.from_pretrained(rag_settings.E5_MODEL_NAME)
e5_model = AutoModel.from_pretrained(rag_settings.E5_MODEL_NAME).to(device)
e5_model.eval()  # Set to evaluation mode (no training)



def _average_pool(last_hidden_states, attention_mask):
    last_hidden = last_hidden_states.masked_fill(
        ~attention_mask[..., None].bool(), 0.0
    )
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]


def encode_e5(texts: List[str]):
    """
    Encode texts into normalized E5 embeddings using pre-loaded model.
    
    PERFORMANCE NOTE:
    - Model is loaded ONCE at module import (singleton pattern)
    - This function just USES the cached model (no reload)
    - Runs on GPU if available, fallback to CPU
    
    Args:
        texts: List of strings to encode
               For questions:  "query: {text}"
               For documents:  "passage: {text}"
    
    Returns:
        numpy array of embeddings (shape: [len(texts), 1024])
    """
    # Tokenize and move to GPU/CPU
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    ).to(device)  # ← Inputs moved to GPU/CPU

    # Inference (no gradient computation for speed)
    with torch.no_grad():
        outputs = e5_model(**inputs)  # ← Model runs on GPU/CPU
        pooled = _average_pool(outputs.last_hidden_state, inputs["attention_mask"])
        embeddings = F.normalize(pooled, p=2, dim=1)

    # Return as numpy (move back to CPU if needed)
    return embeddings.cpu().numpy()
