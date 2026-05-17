"""Shared state for the agent graph."""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # inputs
    run_id: int
    repo_id: int
    user_task: str
    mode: str
    workspace: str

    # planner
    plan: dict[str, Any]
    approved: bool

    # retrieval
    retrieved: list[dict[str, Any]]
    retrieval_summary: str
    retrieval_precision: float

    # coder
    diff: str
    files_changed: int
    insertions: int
    deletions: int
    changed_files: list[str]

    # tester / self-heal
    test_passed: bool
    test_total: int
    test_failed: int
    test_logs: str
    iteration: int
    max_iterations: int

    # reviewer
    review: dict[str, Any]

    # evaluator
    evaluation: dict[str, Any]
    pr_summary: str

    # bookkeeping (collected by the runner, not persisted here)
    _events: list[dict[str, Any]]
