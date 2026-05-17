"""Retrieval agent — hybrid RAG over the indexed repo."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.state import AgentState
from app.config import settings
from app.rag.retriever import retrieve


def retrieve_context(db: Session, state: AgentState) -> tuple[list[dict], str]:
    plan = state.get("plan", {})
    query = plan.get("summary") or state["user_task"]
    # Bias retrieval toward the planned intent keywords.
    query = f"{query} {plan.get('intent', '')} {' '.join(plan.get('target_files', []))}"

    results = retrieve(db, state["repo_id"], query, top_k=settings.top_k)
    payload = [
        {
            "file_path": r.file_path,
            "symbol": r.symbol,
            "kind": r.kind,
            "start_line": r.start_line,
            "end_line": r.end_line,
            "score": round(r.score, 4),
            "preview": r.text[:300],
        }
        for r in results
    ]
    if results:
        files = sorted({r.file_path for r in results})
        summary = (
            f"Top-{len(results)} relevant chunks across {len(files)} files: "
            + ", ".join(files[:6])
        )
    else:
        summary = "No indexed chunks matched; proceeding with repo entrypoint."
    return payload, summary
