"""Tester agent — runs the suite in the sandbox and returns a structured result."""
from __future__ import annotations

from pathlib import Path

from app.agents.state import AgentState
from app.sandbox.runner import run_tests


def run(state: AgentState) -> dict:
    result = run_tests(Path(state["workspace"]))
    return {
        "command": result.command,
        "passed": result.passed,
        "total": result.total_tests,
        "failed": result.failed_tests,
        "logs": result.logs,
    }
