"""Coding agent.

In mock mode this applies a deterministic *skill* for the planned intent: it
writes a real feature module plus a consistent unit test into the workspace using
the MCP ``write_file`` tool, then returns the real git diff. In local/api mode it
asks the LLM to author the feature module body, validates it compiles, and falls
back to the deterministic skill if the model output is unusable — so the pipeline
always yields a runnable patch.
"""
from __future__ import annotations

from pathlib import Path

from app.agents.state import AgentState
from app.config import settings
from app.llm import client
from app.llm.prompts import CODER
from app.mcp.server import ToolRegistry

# ---- Deterministic skills: (module_path, module_src, test_path, test_src) ----

_PKG = "devpilot_changes"


def _skill_files(intent: str) -> dict[str, str]:
    pkg_init = f"{_PKG}/__init__.py"
    files: dict[str, str] = {pkg_init: ""}

    if intent == "health":
        files[f"{_PKG}/health.py"] = (
            '"""Health check added by DevPilot."""\n\n\n'
            "def health() -> dict:\n"
            '    """Return service liveness status."""\n'
            '    return {"status": "ok"}\n'
        )
        files["tests/test_health_devpilot.py"] = (
            f"from {_PKG}.health import health\n\n\n"
            "def test_health_returns_ok():\n"
            '    assert health() == {"status": "ok"}\n'
        )
    elif intent == "cache":
        files[f"{_PKG}/cache.py"] = (
            '"""Tiny TTL cache + memoize decorator added by DevPilot."""\n'
            "import time\nfrom functools import wraps\n\n\n"
            "class TTLCache:\n"
            "    def __init__(self, ttl: float = 60.0):\n"
            "        self.ttl = ttl\n        self._store: dict = {}\n\n"
            "    def get(self, key):\n"
            "        item = self._store.get(key)\n"
            "        if not item:\n            return None\n"
            "        value, ts = item\n"
            "        if time.time() - ts > self.ttl:\n"
            "            self._store.pop(key, None)\n            return None\n"
            "        return value\n\n"
            "    def set(self, key, value):\n"
            "        self._store[key] = (value, time.time())\n\n\n"
            "def cached(ttl: float = 60.0):\n"
            "    cache = TTLCache(ttl)\n\n"
            "    def deco(fn):\n        @wraps(fn)\n"
            "        def inner(*args):\n"
            "            hit = cache.get(args)\n"
            "            if hit is not None:\n                return hit\n"
            "            value = fn(*args)\n            cache.set(args, value)\n"
            "            return value\n        return inner\n    return deco\n"
        )
        files["tests/test_cache_devpilot.py"] = (
            f"from {_PKG}.cache import TTLCache, cached\n\n\n"
            "def test_cache_set_get():\n"
            "    c = TTLCache(ttl=10)\n    c.set('k', 42)\n    assert c.get('k') == 42\n\n\n"
            "def test_cached_memoizes():\n"
            "    calls = {'n': 0}\n\n    @cached(ttl=10)\n    def f(x):\n"
            "        calls['n'] += 1\n        return x * 2\n\n"
            "    assert f(3) == 6\n    assert f(3) == 6\n    assert calls['n'] == 1\n"
        )
    elif intent == "validation":
        files[f"{_PKG}/validation.py"] = (
            '"""Input validation helpers added by DevPilot."""\n\n\n'
            "def validate_non_empty(value: str) -> str:\n"
            "    if value is None or not str(value).strip():\n"
            "        raise ValueError('value must be a non-empty string')\n"
            "    return str(value).strip()\n"
        )
        files["tests/test_validation_devpilot.py"] = (
            "import pytest\n"
            f"from {_PKG}.validation import validate_non_empty\n\n\n"
            "def test_valid():\n    assert validate_non_empty('  hi ') == 'hi'\n\n\n"
            "def test_invalid():\n"
            "    with pytest.raises(ValueError):\n        validate_non_empty('   ')\n"
        )
    elif intent == "pagination":
        files[f"{_PKG}/pagination.py"] = (
            '"""Pagination helper added by DevPilot."""\n\n\n'
            "def paginate(items, limit=10, offset=0):\n"
            "    limit = max(0, int(limit))\n    offset = max(0, int(offset))\n"
            "    return items[offset: offset + limit]\n"
        )
        files["tests/test_pagination_devpilot.py"] = (
            f"from {_PKG}.pagination import paginate\n\n\n"
            "def test_page():\n    assert paginate(list(range(10)), 3, 2) == [2, 3, 4]\n\n\n"
            "def test_clamps():\n    assert paginate(list(range(3)), -1, -5) == []\n"
        )
    elif intent == "logging":
        files[f"{_PKG}/logging_config.py"] = (
            '"""Logger factory added by DevPilot."""\n'
            "import logging\n\n\n"
            "def get_logger(name: str = 'devpilot') -> logging.Logger:\n"
            "    logger = logging.getLogger(name)\n"
            "    if not logger.handlers:\n"
            "        handler = logging.StreamHandler()\n"
            "        handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(message)s'))\n"
            "        logger.addHandler(handler)\n"
            "    logger.setLevel(logging.INFO)\n    return logger\n"
        )
        files["tests/test_logging_devpilot.py"] = (
            "import logging\n"
            f"from {_PKG}.logging_config import get_logger\n\n\n"
            "def test_logs(caplog):\n"
            "    logger = get_logger('t')\n"
            "    with caplog.at_level(logging.INFO):\n        logger.info('hello')\n"
            "    assert 'hello' in caplog.text\n"
        )
    elif intent == "error_handling":
        files[f"{_PKG}/errors.py"] = (
            '"""Safe-call wrapper added by DevPilot."""\n\n\n'
            "def safe_call(fn, *args, default=None):\n"
            "    try:\n        return fn(*args), None\n"
            "    except Exception as exc:  # noqa: BLE001\n"
            "        return default, str(exc)\n"
        )
        files["tests/test_errors_devpilot.py"] = (
            f"from {_PKG}.errors import safe_call\n\n\n"
            "def test_ok():\n    assert safe_call(lambda x: x + 1, 1) == (2, None)\n\n\n"
            "def test_err():\n"
            "    value, err = safe_call(lambda: 1 / 0, default=-1)\n"
            "    assert value == -1 and err\n"
        )
    else:  # generic
        files[f"{_PKG}/feature.py"] = (
            '"""Feature module added by DevPilot."""\n\n\n'
            "def run(x: int) -> int:\n    return x * 2\n"
        )
        files["tests/test_feature_devpilot.py"] = (
            f"from {_PKG}.feature import run\n\n\n"
            "def test_run():\n    assert run(21) == 42\n"
        )
    return files


def _maybe_wire_fastapi_route(workspace: Path, reg: ToolRegistry) -> None:
    """Best-effort: register a /health route on a detected FastAPI app (health intent)."""
    for candidate in ["app/main.py", "main.py", "src/main.py"]:
        res = reg.invoke("read_file", path=candidate)
        if not res.get("ok"):
            continue
        content = res["content"]
        if "FastAPI(" in content and "/health" not in content:
            addition = (
                "\n\n# --- added by DevPilot ---\n"
                "from devpilot_changes.health import health as _devpilot_health\n\n\n"
                '@app.get("/health")\n'
                "def devpilot_health():\n    return _devpilot_health()\n"
            )
            reg.invoke("write_file", path=candidate, content=content + addition)
        return


def _llm_module(intent: str, target_path: str) -> str | None:  # pragma: no cover - needs LLM
    try:
        body = client.complete(
            CODER,
            f"Write a small, self-contained Python module for intent '{intent}'. "
            f"It will live at {target_path}. Output only Python code, no fences.",
        )
        body = body.replace("```python", "").replace("```", "").strip()
        compile(body, target_path, "exec")
        return body + "\n"
    except Exception:
        return None


def apply_changes(state: AgentState, reg: ToolRegistry) -> dict:
    workspace = Path(state["workspace"])
    intent = state.get("plan", {}).get("intent", "generic")
    files = _skill_files(intent)

    # local/api mode: let the LLM author the feature module body (with fallback).
    if settings.mode != "mock":
        module_path = next((p for p in files if p.startswith(f"{_PKG}/") and not p.endswith("__init__.py")), None)
        if module_path:
            llm_body = _llm_module(intent, module_path)
            if llm_body:
                files[module_path] = llm_body

    changed: list[str] = []
    for path, content in files.items():
        res = reg.invoke("write_file", path=path, content=content)
        if res.get("ok"):
            changed.append(path)

    if intent == "health":
        _maybe_wire_fastapi_route(workspace, reg)

    diff = reg.invoke("git_diff")
    return {
        "diff": diff.get("diff", ""),
        "files_changed": diff.get("files_changed", len(changed)),
        "insertions": diff.get("insertions", 0),
        "deletions": diff.get("deletions", 0),
        "changed_files": changed,
    }
