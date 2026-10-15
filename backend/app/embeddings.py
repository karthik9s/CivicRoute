"""Embedding backends.

Default is a small multilingual sentence-transformers model (works for English, Hindi and
other Indian languages). `hash` is a deterministic bag-of-words embedder used in tests and
as a last-resort fallback when the model can't be downloaded.
"""
from __future__ import annotations

import hashlib
import logging
import re
from functools import lru_cache

import numpy as np

from .config import settings

log = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def stem(tok: str) -> str:
    """Tiny suffix stripper so 'fees'~'fee', 'linking'~'link', 'charges'~'charge' for keyword search."""
    for suf in ("ings", "ing", "ies", "es", "ed", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[: -len(suf)] + ("y" if suf == "ies" else "")
    return tok


def keyword_tokens(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]


class HashEmbedder:
    name = "hash"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = tokenize(text)
        for tok in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 8) % 2 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.model = SentenceTransformer(model_name)
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dim = get_dim()
        # E5-family models expect "query: " / "passage: " prefixes.
        self._e5 = "e5" in model_name.lower()

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if self._e5:
            texts = ["passage: " + t for t in texts]
        return self.model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False).astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        if self._e5:
            text = "query: " + text
        return self.model.encode([text], normalize_embeddings=True)[0].astype(np.float32)


@lru_cache(maxsize=1)
def get_embedder():
    if settings.embedding_model == "hash":
        return HashEmbedder()
    try:
        return SentenceTransformerEmbedder(settings.embedding_model)
    except Exception as exc:  # model download failure, missing torch, etc.
        log.warning("Falling back to hash embedder (%s): %s", settings.embedding_model, exc)
        return HashEmbedder()
