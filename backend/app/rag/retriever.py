"""Hybrid retriever.

Combines dense (cosine over embeddings) and sparse (BM25) signals with min-max
normalisation and a configurable ``alpha`` weight, then returns the top-k chunks.
This is the in-process numpy index — it loads a repo's chunk embeddings from the
DB and scores in memory. For very large repos, ``PgVectorStore`` provides an ANN
path on Postgres (see ``app/db/vector_store.py``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import CodeChunk
from app.rag.bm25 import BM25
from app.rag.embeddings import embed_one


@dataclass
class RetrievedChunk:
    chunk_id: int
    file_path: str
    symbol: str
    kind: str
    text: str
    start_line: int
    end_line: int
    score: float
    dense_score: float
    sparse_score: float


def _minmax(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def retrieve(
    db: Session,
    repo_id: int,
    query: str,
    top_k: int | None = None,
    alpha: float | None = None,
) -> list[RetrievedChunk]:
    top_k = top_k or settings.top_k
    alpha = settings.hybrid_alpha if alpha is None else alpha

    chunks: list[CodeChunk] = (
        db.query(CodeChunk).filter(CodeChunk.repo_id == repo_id).all()
    )
    if not chunks:
        return []

    # Dense scores
    mat = np.asarray([c.embedding for c in chunks], dtype=np.float32)
    qv = np.asarray(embed_one(query), dtype=np.float32)
    if mat.shape[1] == qv.shape[0] and mat.size:
        dense = mat @ qv  # both L2-normalised => cosine similarity
    else:
        dense = np.zeros(len(chunks), dtype=np.float32)

    # Sparse scores
    bm25 = BM25([c.chunk_text for c in chunks])
    sparse = np.asarray(bm25.scores(query), dtype=np.float32)

    fused = alpha * _minmax(dense) + (1 - alpha) * _minmax(sparse)
    order = np.argsort(-fused)[:top_k]

    results: list[RetrievedChunk] = []
    for i in order:
        c = chunks[int(i)]
        results.append(
            RetrievedChunk(
                chunk_id=c.id,
                file_path=c.file_path,
                symbol=c.symbol,
                kind=c.kind,
                text=c.chunk_text,
                start_line=c.start_line,
                end_line=c.end_line,
                score=float(fused[i]),
                dense_score=float(dense[i]),
                sparse_score=float(sparse[i]),
            )
        )
    return results
