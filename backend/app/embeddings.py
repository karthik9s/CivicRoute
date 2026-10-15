"""Embedding backends.

Default is the small multilingual E5 model (English, Hindi, Telugu and other Indian languages)
run with ONNX Runtime as an int8-quantized export: ~120 MB of RAM instead of ~500 MB for PyTorch,
so the app fits free 512 MB hosts. `sentence-transformers` is still used if installed and
EMBEDDING_BACKEND=torch. `hash` is a deterministic bag-of-words embedder used in tests and
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


class OnnxEmbedder:
    """multilingual-e5-small via ONNX Runtime: tokenize -> transformer -> mean-pool -> L2-normalize
    (the same pipeline sentence-transformers runs for this model).

    Tokenizes with the model's original SentencePiece file (~5 MB in RAM) instead of tokenizer.json,
    which the `tokenizers` library inflates to ~280 MB. Token ids are identical (XLM-R layout:
    <s>=0, <pad>=1, </s>=2, <unk>=3, SentencePiece ids shifted by 1) - verified on every indexed chunk."""

    MAX_TOKENS = 512

    def __init__(self, model_name: str, repo: str, filename: str):
        import onnxruntime as ort
        import sentencepiece as spm
        from huggingface_hub import hf_hub_download

        self.name = f"{model_name}:onnx-q8"
        self.sp = spm.SentencePieceProcessor(model_file=hf_hub_download(model_name, "sentencepiece.bpe.model"))
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = settings.embedding_threads
        opts.enable_cpu_mem_arena = False  # return memory after big batches (tight hosts)
        self.session = ort.InferenceSession(hf_hub_download(repo, filename), opts, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self.session.get_inputs()}
        self._e5 = "e5" in model_name.lower()
        self.dim = int(self._encode(["dim"]).shape[1])

    def _ids(self, text: str) -> list[int]:
        pieces = [i + 1 if i else 3 for i in self.sp.encode(text.strip())]
        return [0] + pieces[: self.MAX_TOKENS - 2] + [2]

    def _encode(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 16):  # small batches keep peak memory low
            seqs = [self._ids(t) for t in texts[i:i + 16]]
            width = max(len(s) for s in seqs)
            ids = np.ones((len(seqs), width), dtype=np.int64)  # 1 = <pad>
            mask = np.zeros((len(seqs), width), dtype=np.int64)
            for r, s in enumerate(seqs):
                ids[r, :len(s)] = s
                mask[r, :len(s)] = 1
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feed)[0]
            pooled = (hidden * mask[..., None]).sum(1) / np.maximum(mask.sum(1, keepdims=True), 1)
            out.append(pooled / np.linalg.norm(pooled, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), np.float32)
        return self._encode(["passage: " + t if self._e5 else t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode(["query: " + text if self._e5 else text])[0]


class SentenceTransformerEmbedder:
    """Optional PyTorch backend (EMBEDDING_BACKEND=torch, needs `pip install sentence-transformers`)."""

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
        if settings.embedding_backend == "torch":
            return SentenceTransformerEmbedder(settings.embedding_model)
        return OnnxEmbedder(settings.embedding_model, settings.embedding_onnx_repo, settings.embedding_onnx_file)
    except Exception as exc:  # model download failure, missing runtime, etc.
        log.warning("Falling back to hash embedder (%s): %s", settings.embedding_model, exc)
        return HashEmbedder()
