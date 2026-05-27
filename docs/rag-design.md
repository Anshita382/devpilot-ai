# RAG Design

DevPilot indexes repositories and retrieves relevant code with a hybrid of dense
(semantic) and sparse (lexical) signals.

## Chunking

`chunker.py` is AST-aware via symbol regexes for Python/JS/TS/Java/Go: it splits
on function and class boundaries so a chunk is a coherent unit (a function or
class), tagged with its symbol name, kind, and line range. Files that don't match
any symbol pattern (or non-code text) fall back to a line-window splitter with
overlap (`DEVPILOT_MAX_CHUNK_LINES`, `DEVPILOT_CHUNK_OVERLAP_LINES`).

## Embeddings

Two interchangeable embedders behind `get_embedder()`:

- **Deterministic feature-hash** (default): tokenises code (splitting camelCase
  and snake_case), hashes tokens into a 384-dim vector, and L2-normalises. No
  model download, fully reproducible — the same text always yields the same
  vector. This is what makes offline mode and deterministic tests possible.
- **sentence-transformers MiniLM** (optional): real semantic embeddings, same
  384 dimensions, used automatically if the package is installed.

Embeddings are stored as JSON text on `code_chunks.embedding_json`, which keeps
the schema portable between SQLite and Postgres.

## Sparse retrieval (BM25)

A pure-Python Okapi BM25 implementation with a code-aware tokenizer. No external
search engine required.

## Hybrid fusion

`retriever.retrieve()` scores every chunk in the repo two ways:

```
dense  = normalize(cosine(query_embedding, chunk_embeddings))
sparse = normalize(bm25(query, chunk_texts))
fused  = alpha * dense + (1 - alpha) * sparse
```

`alpha` is `DEVPILOT_HYBRID_ALPHA` (default 0.5). Both signals are min-max
normalised before fusion so neither dominates by scale. The top-`DEVPILOT_TOP_K`
chunks (default 8) are returned with their fused, dense, and sparse scores for
transparency.

This in-process numpy index loads a repo's chunk embeddings and scores in memory —
fast and dependency-free for typical repos.

## Scaling to pgvector

When `DEVPILOT_DATABASE_URL` points at Postgres, `PgVectorStore` mirrors chunk
vectors into a `vector` column with an `ivfflat` index and serves approximate
nearest-neighbour search via the `<=>` distance operator. On SQLite it's a no-op
and the numpy path is used. The dense half of the hybrid score can therefore move
to an ANN index for large repos without changing the retrieval contract.

## Measuring retrieval quality

Precision@k is computed in the retrieval node on the clean workspace (before the
coder writes anything). Ground truth is the pre-existing, non-test source file the
change anchors to (the planned target file if it already exists, else the repo
entrypoint). Precision@k is the fraction of the top-k retrieved chunks drawn from
those anchor files. Excluding test files matters: the coder *creates* the task's
test file during the run, and counting it would measure the agent's own output
rather than retrieval quality.
