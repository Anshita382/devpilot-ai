"""Tests for embeddings, BM25, and hybrid retrieval."""
import numpy as np

from app.rag.bm25 import BM25
from app.rag.embeddings import embed_one, embed_texts
from app.rag.ingest import ingest_repo
from app.rag.retriever import retrieve


def test_embeddings_deterministic_and_normalised():
    a = embed_one("def health(): return ok")
    b = embed_one("def health(): return ok")
    assert a == b, "hash embeddings must be deterministic"
    norm = float(np.linalg.norm(np.asarray(a)))
    assert abs(norm - 1.0) < 1e-3, "embeddings should be L2-normalised"


def test_bm25_ranks_relevant_doc_first():
    docs = [
        "the cache stores values with a ttl expiry",
        "completely unrelated text about gardening and soil",
        "user authentication and password hashing",
    ]
    bm = BM25(docs)
    scores = bm.scores("cache ttl expiry")
    assert int(np.argmax(scores)) == 0


def test_hybrid_retrieve_over_ingested_repo(db, sample_repo_path):
    repo = ingest_repo(db, "sample", sample_repo_path)
    db.commit()
    assert repo.n_chunks > 0

    results = retrieve(db, repo.id, "product search by name", top_k=5)
    assert results, "expected retrieval hits"
    # The search function lives in app/main.py — it should surface near the top.
    top_files = [r.file_path for r in results[:5]]
    assert any("main.py" in f for f in top_files)
    # Each result carries both signal components.
    for r in results:
        assert 0.0 <= r.score
        assert hasattr(r, "dense_score") and hasattr(r, "sparse_score")
