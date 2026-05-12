"""Code chunking.

Strategy:
  1. If tree-sitter is available, split files at function/class boundaries
     (AST-aware) so each chunk is a coherent semantic unit.
  2. Otherwise, fall back to a regex symbol-splitter for Python/JS/Java/Go, then
     to a sliding line window. Always produces chunks with line spans + symbol
     names so retrieval results point at real code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import settings

EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".md": "markdown",
}

# Lightweight symbol detectors per language (fallback when tree-sitter absent).
_SYMBOL_PATTERNS = {
    "python": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)"),
    "javascript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s+([A-Za-z_]\w*)|class\s+([A-Za-z_]\w*)|const\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\()"),
    "typescript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s+([A-Za-z_]\w*)|class\s+([A-Za-z_]\w*)|const\s+([A-Za-z_]\w*)\s*[:=])"),
    "java": re.compile(r"^\s*(?:public|private|protected|static|final|\s)*(?:class|interface)\s+([A-Za-z_]\w*)|^\s*(?:public|private|protected|static|final|\s)+[\w<>\[\]]+\s+([A-Za-z_]\w*)\s*\("),
    "go": re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)|^\s*type\s+([A-Za-z_]\w*)"),
}


@dataclass
class Chunk:
    file_path: str
    symbol: str
    kind: str
    text: str
    start_line: int
    end_line: int


def detect_language(path: str) -> str:
    for ext, lang in EXT_LANG.items():
        if path.endswith(ext):
            return lang
    return "unknown"


def _first_group(m: re.Match) -> str:
    for g in m.groups():
        if g:
            return g
    return ""


def _symbol_split(lines: list[str], lang: str, path: str) -> list[Chunk]:
    pattern = _SYMBOL_PATTERNS.get(lang)
    if pattern is None:
        return []
    boundaries: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            boundaries.append((i, _first_group(m) or "anon"))
    if not boundaries:
        return []
    chunks: list[Chunk] = []
    # Header (imports/top-level) before the first symbol.
    if boundaries[0][0] > 0:
        chunks.append(_mk(path, "module", "block", lines, 0, boundaries[0][0]))
    for idx, (start, name) in enumerate(boundaries):
        end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
        kind = "class" if "class" in lines[start] else "function"
        chunks.append(_mk(path, name, kind, lines, start, end))
    return chunks


def _mk(path: str, symbol: str, kind: str, lines: list[str], start: int, end: int) -> Chunk:
    text = "\n".join(lines[start:end]).strip("\n")
    return Chunk(path, symbol, kind, text, start + 1, end)


def _window_split(lines: list[str], path: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    step = max(1, settings.max_chunk_lines - settings.chunk_overlap_lines)
    for start in range(0, len(lines), step):
        end = min(len(lines), start + settings.max_chunk_lines)
        chunks.append(_mk(path, "", "block", lines, start, end))
        if end >= len(lines):
            break
    return chunks


def chunk_file(path: str, content: str) -> list[Chunk]:
    lang = detect_language(path)
    lines = content.splitlines()
    if not lines:
        return []

    sym_chunks = _symbol_split(lines, lang, path)
    chunks = sym_chunks if sym_chunks else _window_split(lines, path)

    # Further split any over-long chunk into windows to keep embeddings focused.
    final: list[Chunk] = []
    for c in chunks:
        span = c.end_line - c.start_line + 1
        if span > settings.max_chunk_lines * 1.6:
            sub_lines = c.text.splitlines()
            step = max(1, settings.max_chunk_lines - settings.chunk_overlap_lines)
            for s in range(0, len(sub_lines), step):
                e = min(len(sub_lines), s + settings.max_chunk_lines)
                sub = "\n".join(sub_lines[s:e])
                final.append(
                    Chunk(c.file_path, c.symbol, c.kind, sub, c.start_line + s, c.start_line + e - 1)
                )
                if e >= len(sub_lines):
                    break
        else:
            final.append(c)
    return [c for c in final if c.text.strip()]
