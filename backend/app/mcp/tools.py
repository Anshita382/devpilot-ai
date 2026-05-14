"""Tool implementations exposed through the MCP layer.

Every tool operates on a sandboxed workspace directory and returns a plain dict.
These are *real* operations (filesystem, git, ripgrep-style search, pytest) — the
agents call them through ``app.mcp.server.ToolRegistry`` so each invocation is
recorded as a ToolCall for observability.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _safe(workspace: Path, rel: str) -> Path:
    p = (workspace / rel).resolve()
    if not str(p).startswith(str(workspace.resolve())):
        raise ValueError(f"path escapes workspace: {rel}")
    return p


def read_file(workspace: Path, path: str) -> dict:
    p = _safe(workspace, path)
    if not p.exists():
        return {"ok": False, "error": "not found", "path": path}
    return {"ok": True, "path": path, "content": p.read_text(encoding="utf-8", errors="ignore")}


def write_file(workspace: Path, path: str, content: str) -> dict:
    p = _safe(workspace, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "created": not existed, "bytes": len(content)}


def list_files(workspace: Path, subdir: str = "") -> dict:
    base = _safe(workspace, subdir) if subdir else workspace
    out = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts:
            out.append(str(p.relative_to(workspace)))
    return {"ok": True, "files": out[:2000]}


def search_code(workspace: Path, query: str, max_results: int = 40) -> dict:
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    hits = []
    for p in workspace.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    hits.append({"file": str(p.relative_to(workspace)), "line": i, "text": line.strip()[:200]})
                    if len(hits) >= max_results:
                        return {"ok": True, "hits": hits}
        except Exception:
            continue
    return {"ok": True, "hits": hits}


def _git(workspace: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=workspace, capture_output=True, text=True, timeout=timeout
    )


def git_init_if_needed(workspace: Path) -> dict:
    if (workspace / ".git").exists():
        return {"ok": True, "initialized": False}
    _git(workspace, "init", "-q")
    _git(workspace, "add", "-A")
    _git(workspace, "-c", "user.email=devpilot@local", "-c", "user.name=DevPilot",
         "commit", "-q", "-m", "baseline")
    return {"ok": True, "initialized": True}


def git_diff(workspace: Path) -> dict:
    git_init_if_needed(workspace)
    _git(workspace, "add", "-A")
    cp = _git(workspace, "diff", "--cached")
    stat = _git(workspace, "diff", "--cached", "--numstat").stdout.strip().splitlines()
    insertions = deletions = files = 0
    for line in stat:
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            insertions += int(parts[0])
            deletions += int(parts[1])
            files += 1
    return {
        "ok": True,
        "diff": cp.stdout,
        "files_changed": files,
        "insertions": insertions,
        "deletions": deletions,
    }


def create_patch(workspace: Path, out_name: str = "devpilot.patch") -> dict:
    diff = git_diff(workspace)["diff"]
    (workspace / out_name).write_text(diff, encoding="utf-8")
    return {"ok": True, "patch_file": out_name, "size": len(diff)}


def apply_patch(workspace: Path, diff: str) -> dict:
    proc = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=workspace, input=diff, capture_output=True, text=True,
    )
    return {"ok": proc.returncode == 0, "stderr": proc.stderr}


def run_linter(workspace: Path) -> dict:
    """Best-effort compile-check as a lightweight linter (no extra deps)."""
    errors = []
    for p in workspace.rglob("*.py"):
        if ".git" in p.parts:
            continue
        try:
            compile(p.read_text(encoding="utf-8", errors="ignore"), str(p), "exec")
        except SyntaxError as e:
            errors.append(f"{p.relative_to(workspace)}:{e.lineno}: {e.msg}")
    return {"ok": len(errors) == 0, "errors": errors}


def summarize_repo(workspace: Path) -> dict:
    files = list_files(workspace)["files"]
    by_ext: dict[str, int] = {}
    for f in files:
        ext = Path(f).suffix or "(none)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
    return {"ok": True, "n_files": len(files), "by_extension": by_ext}
