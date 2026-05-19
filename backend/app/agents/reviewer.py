"""Reviewer agent — checks the generated diff for quality and risk."""
from __future__ import annotations

import json
import re

from app.agents.state import AgentState
from app.config import settings
from app.llm import client
from app.llm.prompts import REVIEWER

_RISKY = [
    (r"\beval\s*\(", "use of eval()"),
    (r"\bexec\s*\(", "use of exec()"),
    (r"shell\s*=\s*True", "subprocess with shell=True"),
    (r"password\s*=\s*['\"]", "hard-coded password literal"),
    (r"verify\s*=\s*False", "TLS verification disabled"),
]


def _heuristic_review(state: AgentState) -> dict:
    diff = state.get("diff", "")
    issues: list[str] = []
    suggestions: list[str] = []

    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    added_text = "\n".join(added)

    for pattern, label in _RISKY:
        if re.search(pattern, added_text):
            issues.append(f"Potential risk: {label}")

    has_test = any("test" in f.lower() for f in state.get("changed_files", []))
    if not has_test:
        suggestions.append("Add a unit test covering the new behaviour.")

    if state.get("insertions", 0) > 400:
        suggestions.append("Large diff — consider splitting into smaller commits.")

    if not state.get("test_passed", False):
        issues.append("Tests are not passing for the current diff.")

    approved = not issues
    return {
        "approved": approved,
        "issues": issues,
        "suggestions": suggestions or ["Looks clean. Consider documenting the new module."],
    }


def review(state: AgentState) -> dict:
    base = _heuristic_review(state)
    if settings.mode == "mock":
        return base
    try:  # pragma: no cover - needs LLM
        raw = client.complete(REVIEWER, f"Diff:\n{state.get('diff', '')[:6000]}")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            llm = json.loads(match.group(0))
            base["issues"] = list({*base["issues"], *llm.get("issues", [])})
            base["suggestions"] = list({*base["suggestions"], *llm.get("suggestions", [])})
            base["approved"] = base["approved"] and bool(llm.get("approved", True))
    except Exception:
        pass
    return base
