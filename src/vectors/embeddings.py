from typing import List

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel

from src.config import E5_MODEL_NAME

device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(E5_MODEL_NAME)
e5_model = AutoModel.from_pretrained(E5_MODEL_NAME).to(device)
e5_model.eval()


def _average_pool(last_hidden_states, attention_mask):
    last_hidden = last_hidden_states.masked_fill(
        ~attention_mask[..., None].bool(), 0.0
    )
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]


def encode_e5(texts: List[str]):
    """
    Encode texts into normalized E5 embeddings.

    For questions:  "query: ... "
    For nodes/docs: "passage: ... "
    """
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = e5_model(**inputs)
        pooled = _average_pool(outputs.last_hidden_state, inputs["attention_mask"])
        embeddings = F.normalize(pooled, p=2, dim=1)

    return embeddings.cpu().numpy()
