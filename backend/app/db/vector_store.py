"""Optional pgvector-backed vector index (production / scale path).

The default retriever uses an in-process numpy index that needs no setup. When
running on the bundled Postgres (``DEVPILOT_DATABASE_URL=postgresql://...``) with
the pgvector extension, this module mirrors chunk embeddings into a ``vector``
column and exposes cosine ANN search via the ``<=>`` operator.

It is intentionally decoupled from the ORM so the portable schema stays simple;
call ``sync_repo`` after ingest and ``search`` at query time.
"""
from __future__ import annotations

import json

from sqlalchemy import text

from app.config import settings
from app.db.session import engine

_DIM = settings.embedding_dim


def available() -> bool:
    if not settings.using_postgres:
        return False
    try:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).first()
            return r is not None
    except Exception:
        return False


def ensure_schema() -> None:
    if not available():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS chunk_vectors (
                    chunk_id INTEGER PRIMARY KEY,
                    repo_id  INTEGER NOT NULL,
                    embedding vector({_DIM})
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunk_vectors_ann "
                "ON chunk_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
        )


def sync_repo(repo_id: int, rows: list[tuple[int, list[float]]]) -> None:
    """rows: list of (chunk_id, embedding)."""
    if not available():
        return
    ensure_schema()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM chunk_vectors WHERE repo_id=:r"), {"r": repo_id})
        for chunk_id, emb in rows:
            conn.execute(
                text(
                    "INSERT INTO chunk_vectors (chunk_id, repo_id, embedding) "
                    "VALUES (:c, :r, :e)"
                ),
                {"c": chunk_id, "r": repo_id, "e": json.dumps(emb)},
            )


def search(repo_id: int, query_embedding: list[float], top_k: int) -> list[tuple[int, float]]:
    if not available():
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT chunk_id, 1 - (embedding <=> :q) AS sim "
                "FROM chunk_vectors WHERE repo_id=:r "
                "ORDER BY embedding <=> :q LIMIT :k"
            ),
            {"q": json.dumps(query_embedding), "r": repo_id, "k": top_k},
        ).all()
    return [(int(r[0]), float(r[1])) for r in rows]
