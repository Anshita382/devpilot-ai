"""Embeddings.

Tries to load sentence-transformers for real semantic vectors. If the package or
model is unavailable (offline / mock mode), falls back to a *deterministic*
feature-hash embedding so the whole pipeline still produces stable, comparable
vectors with zero downloads. Both produce ``settings.embedding_dim`` vectors.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache

import numpy as np

from app.config import settings

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class _HashEmbedder:
    """Deterministic, dependency-free embedder.

    Uses the hashing trick over code tokens (snake_case + camelCase aware) into a
    fixed-dim space, then L2-normalises. Not semantic, but stable and good enough
    to make hybrid retrieval and the full agent loop work offline.
    """

    name = "hash-fallback"

    def __init__(self, dim: int):
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        raw = _WORD.findall(text.lower())
        out: list[str] = []
        for tok in raw:
            out.append(tok)
            # split camelCase into subtokens for better recall
            parts = re.findall(r"[a-z]+|[0-9]+", tok)
            if len(parts) > 1:
                out.extend(parts)
        return out

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in self._tokens(text):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
                vecs[i, idx] += sign
            norm = np.linalg.norm(vecs[i])
            if norm > 0:
                vecs[i] /= norm
        return vecs


class _STEmbedder:
    name = "sentence-transformers"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float32,
        )


@lru_cache
def get_embedder():
    """Return the best available embedder. Cached for the process lifetime."""
    if settings.mode != "mock":
        try:
            emb = _STEmbedder(settings.embedding_model)
            return emb
        except Exception:
            pass
    return _HashEmbedder(settings.embedding_dim)


def embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, settings.embedding_dim), dtype=np.float32)
    return get_embedder().encode(texts)


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0].tolist()
