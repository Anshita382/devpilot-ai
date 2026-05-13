"""Repository ingestion pipeline.

Clones a GitHub URL (or copies a local path) into an isolated workspace, walks
source files, chunks them (AST-aware), embeds the chunks, and persists everything
to the DB. Designed to be safe and offline-friendly:

  * binary / vendored / oversized files are skipped
  * a local filesystem path is accepted as a "url" so the bundled sample repos in
    ``examples/`` can be ingested with no network access.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import WORKSPACES_DIR
from app.db import vector_store
from app.db.models import CodeChunk, Repository, RepoFile
from app.rag.chunker import chunk_file, detect_language
from app.rag.embeddings import embed_texts

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".pytest_cache", ".mypy_cache", "target", "vendor", ".devpilot_data",
}
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".rs",
    ".md", ".txt", ".toml", ".cfg", ".yaml", ".yml", ".json",
}
MAX_FILE_BYTES = 200_000


def _clone_or_copy(url: str, dest: Path) -> str:
    if dest.exists():
        shutil.rmtree(dest)
    src = Path(url).expanduser()
    if src.exists():  # local path (sample repos, offline)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*IGNORE_DIRS))
        return "local"
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return "git"


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        # Check ignore dirs relative to the repo root — the workspace itself may
        # live under a path segment (e.g. .devpilot_data) that is in IGNORE_DIRS.
        rel_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() not in SOURCE_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _dominant_language(langs: list[str]) -> str:
    counts: dict[str, int] = {}
    for lang in langs:
        if lang in ("unknown", "markdown"):
            continue
        counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else "unknown"


def ingest_repo(db: Session, name: str, url: str) -> Repository:
    repo = Repository(name=name, url=url, status="cloning")
    db.add(repo)
    db.flush()

    dest = WORKSPACES_DIR / f"repo_{repo.id}"
    t0 = time.time()
    try:
        _clone_or_copy(url, dest)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - network dependent
        repo.status = "error"
        db.flush()
        raise RuntimeError(f"git clone failed: {exc.stderr or exc}") from exc

    repo.local_path = str(dest)
    repo.status = "indexing"
    db.flush()

    languages: list[str] = []
    all_chunks: list[CodeChunk] = []
    texts: list[str] = []

    for path in _iter_source_files(dest):
        rel = str(path.relative_to(dest))
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lang = detect_language(rel)
        languages.append(lang)
        db.add(
            RepoFile(
                repo_id=repo.id,
                file_path=rel,
                language=lang,
                n_lines=content.count("\n") + 1,
                size_bytes=len(content.encode("utf-8")),
            )
        )
        for ch in chunk_file(rel, content):
            cc = CodeChunk(
                repo_id=repo.id,
                file_path=ch.file_path,
                symbol=ch.symbol,
                kind=ch.kind,
                chunk_text=ch.text,
                start_line=ch.start_line,
                end_line=ch.end_line,
            )
            all_chunks.append(cc)
            texts.append(f"{ch.file_path} {ch.symbol}\n{ch.text}")

    # Batch-embed everything in one pass.
    vectors = embed_texts(texts)
    for cc, vec in zip(all_chunks, vectors):
        cc.embedding = vec.tolist()
        db.add(cc)
    db.flush()

    # Mirror into pgvector when available (no-op on SQLite).
    vector_store.sync_repo(repo.id, [(c.id, c.embedding) for c in all_chunks])

    repo.n_files = len(languages)
    repo.n_chunks = len(all_chunks)
    repo.language = _dominant_language(languages)
    repo.status = "ready"
    db.flush()
    repo._ingest_seconds = round(time.time() - t0, 2)  # type: ignore[attr-defined]
    return repo
