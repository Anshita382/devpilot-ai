"""Tests for MCP tools and the tool registry."""
from pathlib import Path

from app.mcp import tools
from app.mcp.server import ToolRegistry, list_tools


def test_list_tools_has_schemas():
    defs = list_tools()
    names = {d["name"] for d in defs}
    assert {"read_file", "write_file", "git_diff", "search_code"} <= names
    for d in defs:
        assert "description" in d and "input_schema" in d


def test_write_read_roundtrip(tmp_path):
    ws = tmp_path
    tools.write_file(ws, "pkg/mod.py", "X = 1\n")
    out = tools.read_file(ws, "pkg/mod.py")
    assert "X = 1" in out["content"]


def test_path_traversal_blocked(tmp_path):
    try:
        tools.write_file(tmp_path, "../escape.py", "danger")
        assert False, "expected path traversal to be blocked"
    except ValueError:
        pass


def test_git_diff_after_change(tmp_path):
    ws = tmp_path
    tools.write_file(ws, "a.py", "print(1)\n")
    tools.git_init_if_needed(ws)
    tools.git_diff(ws)  # baseline
    tools.write_file(ws, "b.py", "print(2)\n")
    diff = tools.git_diff(ws)
    assert "b.py" in diff["diff"]


def test_registry_logs_tool_calls(tmp_path):
    reg = ToolRegistry(Path(tmp_path))
    res = reg.invoke("write_file", path="x.py", content="Y = 2\n")
    assert res["ok"] is True
    read = reg.invoke("read_file", path="x.py")
    assert "Y = 2" in read["content"]
