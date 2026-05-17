"""Planner agent — turns a task + repo summary into a structured plan."""
from __future__ import annotations

import json
import re

from app.agents.state import AgentState
from app.config import settings
from app.llm import client
from app.llm.prompts import PLANNER

_INTENTS = [
    ("health", ["health", "healthcheck", "liveness", "readiness"]),
    ("cache", ["cache", "caching", "redis", "memoize"]),
    ("validation", ["validation", "validate", "input check"]),
    ("pagination", ["pagination", "paginate", "limit", "offset", "page"]),
    ("logging", ["logging", "log ", "logs"]),
    ("error_handling", ["error handling", "exception", "try/except", "error"]),
]


def classify_intent(task: str) -> str:
    t = task.lower()
    for intent, keywords in _INTENTS:
        if any(k in t for k in keywords):
            return intent
    return "generic"


def _mock_plan(task: str, repo_summary: dict) -> dict:
    intent = classify_intent(task)
    target = repo_summary.get("entrypoint", "app/main.py")
    plans = {
        "health": {
            "subtasks": [
                "Add a GET /health endpoint returning service status",
                "Write a unit test asserting 200 and {'status': 'ok'}",
            ],
            "target_files": [target, "tests/test_health_devpilot.py"],
        },
        "cache": {
            "subtasks": [
                "Add a small TTL cache utility",
                "Apply caching to a read-heavy function",
                "Add a unit test for cache hits",
            ],
            "target_files": ["app/cache.py", "tests/test_cache_devpilot.py"],
        },
        "validation": {
            "subtasks": [
                "Add input validation helper",
                "Reject invalid input with a clear error",
                "Add a unit test for the validator",
            ],
            "target_files": ["app/validation.py", "tests/test_validation_devpilot.py"],
        },
        "pagination": {
            "subtasks": [
                "Add limit/offset pagination helper",
                "Add a unit test covering bounds",
            ],
            "target_files": ["app/pagination.py", "tests/test_pagination_devpilot.py"],
        },
        "logging": {
            "subtasks": [
                "Add a configured logger factory",
                "Add a unit test asserting log output",
            ],
            "target_files": ["app/logging_config.py", "tests/test_logging_devpilot.py"],
        },
        "error_handling": {
            "subtasks": [
                "Add a safe-call wrapper that catches and reports errors",
                "Add a unit test for the wrapper",
            ],
            "target_files": ["app/errors.py", "tests/test_errors_devpilot.py"],
        },
        "generic": {
            "subtasks": [
                "Add the requested utility module",
                "Add a unit test for it",
            ],
            "target_files": ["app/devpilot_feature.py", "tests/test_feature_devpilot.py"],
        },
    }
    base = plans[intent]
    risk = "low" if intent in ("health", "logging", "generic") else "medium"
    return {
        "intent": intent,
        "summary": f"Implement '{task.strip()}' with accompanying tests.",
        "subtasks": base["subtasks"],
        "target_files": base["target_files"],
        "risk": risk,
        "tools": ["search_code", "read_file", "write_file", "run_tests", "git_diff"],
    }


def plan(state: AgentState, repo_summary: dict) -> dict:
    task = state["user_task"]
    if settings.mode == "mock":
        return _mock_plan(task, repo_summary)
    # local / api mode
    try:
        raw = client.complete(PLANNER, f"Task: {task}\nRepo summary: {json.dumps(repo_summary)}")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {}
        parsed.setdefault("intent", classify_intent(task))
        parsed.setdefault("tools", ["search_code", "write_file", "run_tests"])
        return parsed
    except Exception:
        return _mock_plan(task, repo_summary)
