"""Evaluation agent — scores the run and drafts the PR summary."""
from __future__ import annotations

from pathlib import Path

from app.agents.state import AgentState


def _is_test_path(path: str) -> bool:
    p = path.lower()
    return "test" in p or p.startswith("tests/") or "/tests/" in p


def _precision_at_k(state: AgentState) -> float:
    """Proxy retrieval precision, measured against the *pre-existing* source
    files the change anchors to.

    Ground truth = planned ``target_files`` that already existed in the repo and
    are not test files; if a task only introduces brand-new files we fall back to
    the repo entrypoint (where the feature is wired in). Precision@k is the
    fraction of retrieved chunks drawn from those anchor files.

    Test files are excluded because the coder *creates* the task's test file
    during the run — counting it would measure the agent's own output, not the
    quality of retrieval. To avoid that contamination entirely, the value is
    computed in the retrieval node on the clean workspace and stashed in
    ``state['retrieval_precision']``; this function is the fallback.
    """
    cached = state.get("retrieval_precision")
    if cached is not None:
        return cached

    retrieved = state.get("retrieved", [])
    if not retrieved:
        return 0.0

    workspace = Path(state.get("workspace", "."))
    targets = [
        t for t in state.get("plan", {}).get("target_files", [])
        if not _is_test_path(t) and (workspace / t).exists()
    ]
    if not targets:
        for candidate in ("app/main.py", "main.py", "src/main.py", "app.py"):
            if (workspace / candidate).exists():
                targets = [candidate]
                break
    if not targets:
        return 0.0

    hits = sum(
        1 for r in retrieved
        if any(a in r["file_path"] or r["file_path"] in a for a in targets)
    )
    return round(hits / len(retrieved), 3)


def precision_at_retrieval(retrieved: list[dict], plan: dict, workspace: str) -> float:
    """Compute precision@k on the clean workspace, right after retrieval and
    before any code is written. Used by the graph to stash an uncontaminated value."""
    state = {"retrieved": retrieved, "plan": plan, "workspace": workspace}
    return _precision_at_k(state)


def evaluate(state: AgentState, tool_success_rate: float, latency_ms: int) -> dict:
    test_pass_rate = 1.0 if state.get("test_passed") else 0.0
    completed = bool(state.get("test_passed")) and bool(state.get("review", {}).get("approved"))
    precision = _precision_at_k(state)
    retries = state.get("iteration", 1) - 1

    score = round(
        0.5 * (1.0 if completed else 0.0)
        + 0.2 * test_pass_rate
        + 0.2 * precision
        + 0.1 * tool_success_rate,
        3,
    )
    report = {
        "task_completed": completed,
        "test_pass_rate": test_pass_rate,
        "retrieval_precision_at_k": precision,
        "repair_iterations": retries,
        "latency_ms": latency_ms,
        "tool_success_rate": round(tool_success_rate, 3),
        "score": score,
    }
    return report


def pr_summary(state: AgentState) -> str:
    plan = state.get("plan", {})
    changed = state.get("changed_files", [])
    review = state.get("review", {})
    status = "✅ tests passing" if state.get("test_passed") else "❌ tests failing"
    lines = [
        f"### DevPilot AI — {plan.get('summary', state['user_task'])}",
        "",
        f"**Status:** {status} ({state.get('test_total', 0)} tests, "
        f"{state.get('test_failed', 0)} failed) · {state.get('iteration', 1) - 1} repair iteration(s)",
        "",
        "**Plan**",
    ]
    for st in plan.get("subtasks", []):
        lines.append(f"- {st}")
    lines += ["", "**Files changed**"]
    for f in changed:
        lines.append(f"- `{f}`")
    if review.get("suggestions"):
        lines += ["", "**Reviewer notes**"]
        for s in review["suggestions"]:
            lines.append(f"- {s}")
    lines += [
        "",
        f"_Diff: {state.get('files_changed', 0)} file(s), "
        f"+{state.get('insertions', 0)} / -{state.get('deletions', 0)}._",
    ]
    return "\n".join(lines)
