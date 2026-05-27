"""Seed script: ingest the bundled sample repo and run one agent workflow.

Useful for populating the dashboard with data for screenshots:

    cd backend && python ../scripts/seed_demo.py

Runs entirely in mock mode (no API keys, no external services).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the backend package importable regardless of where this is invoked.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.agents.graph import run_agent_workflow  # noqa: E402
from app.db.models import AgentRun  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.rag.ingest import ingest_repo  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-fastapi-repo"

DEMO_TASKS = [
    "Add a health check endpoint",
    "Add Redis caching to the product search API",
    "Add input validation to the search endpoint",
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        print(f"Ingesting sample repo from {SAMPLE} ...")
        repo = ingest_repo(db, "sample-fastapi-repo", str(SAMPLE))
        db.commit()
        print(f"  -> repo #{repo.id}: {repo.n_files} files, {repo.n_chunks} chunks ({repo.language})")

        for task in DEMO_TASKS:
            run = AgentRun(repo_id=repo.id, user_task=task, mode="mock")
            db.add(run)
            db.flush()
            state = run_agent_workflow(db, run)
            db.commit()
            ev = state.get("evaluation", {})
            print(
                f"  -> run #{run.id} [{task}]: status={run.status} "
                f"score={ev.get('score')} pass={ev.get('test_pass_rate')} "
                f"p@k={ev.get('retrieval_precision_at_k')} latency={run.total_latency_ms}ms"
            )
        print("\nDone. Start the API (uvicorn app.main:app) and open the dashboard.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
