"""MCP-style tool registry.

Holds tool definitions (name, description, JSON input schema) and dispatches
invocations to ``app.mcp.tools``. Every call can be recorded as a ToolCall row for
observability. The registry is exposed over HTTP at ``/api/mcp/tools`` and is also
re-exported by ``run_stdio_server`` as a real MCP stdio server when the optional
``mcp`` package is installed.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from app.db.models import ToolCall
from app.mcp import tools as T


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    fn: Callable = field(repr=False)


def _schema(**props) -> dict:
    return {"type": "object", "properties": props}


TOOLS: dict[str, ToolDef] = {
    "read_file": ToolDef("read_file", "Read a file from the repo workspace",
                         _schema(path={"type": "string"}), T.read_file),
    "write_file": ToolDef("write_file", "Write/overwrite a file in the workspace",
                          _schema(path={"type": "string"}, content={"type": "string"}), T.write_file),
    "list_files": ToolDef("list_files", "List files in the workspace",
                          _schema(subdir={"type": "string"}), T.list_files),
    "search_code": ToolDef("search_code", "Search code by substring",
                           _schema(query={"type": "string"}), T.search_code),
    "run_tests": ToolDef("run_tests", "Run the project's test suite in a sandbox",
                         _schema(), None),  # handled by sandbox runner
    "run_linter": ToolDef("run_linter", "Static syntax check of Python sources",
                          _schema(), T.run_linter),
    "git_diff": ToolDef("git_diff", "Get the staged unified diff of changes",
                        _schema(), T.git_diff),
    "apply_patch": ToolDef("apply_patch", "Apply a unified diff to the workspace",
                           _schema(diff={"type": "string"}), T.apply_patch),
    "create_patch": ToolDef("create_patch", "Write the current diff to a .patch file",
                            _schema(out_name={"type": "string"}), T.create_patch),
    "summarize_repo": ToolDef("summarize_repo", "Summarise the repo file inventory",
                              _schema(), T.summarize_repo),
}


def list_tools() -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS.values()
    ]


class ToolRegistry:
    """In-process MCP-style dispatcher bound to a workspace + run."""

    def __init__(self, workspace: Path, db: Session | None = None, run_id: int | None = None):
        self.workspace = workspace
        self.db = db
        self.run_id = run_id

    def invoke(self, name: str, **kwargs) -> dict:
        if name not in TOOLS:
            raise KeyError(f"unknown tool: {name}")
        fn = TOOLS[name].fn
        if fn is None:
            raise RuntimeError(f"tool {name} is handled by the sandbox runner, not the registry")
        t0 = time.time()
        try:
            result = fn(self.workspace, **kwargs)
            ok = bool(result.get("ok", True))
        except Exception as exc:  # record failures too
            result = {"ok": False, "error": str(exc)}
            ok = False
        latency = int((time.time() - t0) * 1000)
        self._record(name, kwargs, result, ok, latency)
        return result

    def _record(self, name: str, kwargs: dict, result: dict, ok: bool, latency: int) -> None:
        if self.db is None or self.run_id is None:
            return
        self.db.add(
            ToolCall(
                run_id=self.run_id,
                tool_name=name,
                tool_input=json.dumps(kwargs)[:4000],
                tool_output=json.dumps(result)[:8000],
                success=ok,
                latency_ms=latency,
            )
        )
        self.db.flush()


def run_stdio_server() -> None:  # pragma: no cover - optional, requires `mcp`
    """Expose the same tools as a real MCP stdio server (optional)."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "The 'mcp' package is not installed. `pip install mcp` to run the stdio server."
        ) from exc

    from app.config import WORKSPACES_DIR

    server = FastMCP("devpilot-tools")
    ws = WORKSPACES_DIR

    for tdef in TOOLS.values():
        if tdef.fn is None:
            continue

        def make(fn):
            def handler(**kwargs):
                return fn(ws, **kwargs)
            return handler

        server.add_tool(make(tdef.fn), name=tdef.name, description=tdef.description)
    server.run()


if __name__ == "__main__":  # pragma: no cover
    run_stdio_server()
