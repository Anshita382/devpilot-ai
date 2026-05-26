"""DevPilot AI evaluation harness.

Runs a fixed benchmark of engineering tasks against the bundled sample repo and
reports aggregate metrics: task-completion rate, test-pass rate, retrieval
precision@k, mean repair iterations, mean latency, and tool-call success rate.

These numbers are produced by an actual run — the README quotes whatever this
prints, so the benchmark is reproducible:

    python -m eval.run_eval            # human-readable table
    python -m eval.run_eval --json     # machine-readable JSON
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from app.db.models import AgentRun
from app.db.session import SessionLocal, init_db
from app.rag.ingest import ingest_repo
from app.agents.graph import run_agent_workflow

# Benchmark task set — one per supported intent plus a generic catch-all.
TASKS = [
    "Add a health check endpoint",
    "Add Redis caching to the product search API",
    "Add input validation to the search endpoint",
    "Add pagination to the product list endpoint",
    "Add structured logging to the service",
    "Add error handling to the product lookup",
    "Add a utility helper module",
]

SAMPLE_REPO = Path(__file__).resolve().parents[2] / "examples" / "sample-fastapi-repo"


def run_benchmark() -> dict:
    init_db()
    db = SessionLocal()
    try:
        repo = ingest_repo(db, "eval-sample", str(SAMPLE_REPO))
        db.commit()

        rows = []
        t_start = time.perf_counter()
        for task in TASKS:
            run = AgentRun(repo_id=repo.id, user_task=task, mode="mock")
            db.add(run)
            db.flush()
            state = run_agent_workflow(db, run)
            db.commit()
            report = state.get("evaluation", {})
            rows.append(
                {
                    "task": task,
                    "intent": state.get("plan", {}).get("intent", "?"),
                    "completed": report.get("task_completed", False),
                    "test_pass_rate": report.get("test_pass_rate", 0.0),
                    "precision_at_k": report.get("retrieval_precision_at_k", 0.0),
                    "repair_iterations": report.get("repair_iterations", 0),
                    "latency_ms": report.get("latency_ms", 0),
                    "tool_success_rate": report.get("tool_success_rate", 0.0),
                    "score": report.get("score", 0.0),
                }
            )
        wall_s = round(time.perf_counter() - t_start, 2)

        n = len(rows)
        agg = {
            "n_tasks": n,
            "task_completion_rate": round(sum(r["completed"] for r in rows) / n, 3),
            "mean_test_pass_rate": round(statistics.mean(r["test_pass_rate"] for r in rows), 3),
            "mean_precision_at_k": round(statistics.mean(r["precision_at_k"] for r in rows), 3),
            "mean_repair_iterations": round(statistics.mean(r["repair_iterations"] for r in rows), 3),
            "mean_latency_ms": int(statistics.mean(r["latency_ms"] for r in rows)),
            "mean_tool_success_rate": round(statistics.mean(r["tool_success_rate"] for r in rows), 3),
            "mean_score": round(statistics.mean(r["score"] for r in rows), 3),
            "wall_seconds": wall_s,
        }
        return {"aggregate": agg, "rows": rows}
    finally:
        db.close()


def _print_table(result: dict) -> None:
    rows = result["rows"]
    agg = result["aggregate"]
    print("\nDevPilot AI — Evaluation Benchmark")
    print("=" * 78)
    print(f"{'Task':<42}{'intent':<14}{'pass':<6}{'p@k':<6}{'score':<6}")
    print("-" * 78)
    for r in rows:
        print(
            f"{r['task'][:40]:<42}{r['intent']:<14}"
            f"{r['test_pass_rate']:<6}{r['precision_at_k']:<6}{r['score']:<6}"
        )
    print("=" * 78)
    print(f"Tasks evaluated          : {agg['n_tasks']}")
    print(f"Task completion rate     : {agg['task_completion_rate']*100:.1f}%")
    print(f"Mean test-pass rate      : {agg['mean_test_pass_rate']*100:.1f}%")
    print(f"Mean retrieval precision@k: {agg['mean_precision_at_k']*100:.1f}%")
    print(f"Mean repair iterations   : {agg['mean_repair_iterations']}")
    print(f"Mean latency / task      : {agg['mean_latency_ms']} ms")
    print(f"Mean tool-call success   : {agg['mean_tool_success_rate']*100:.1f}%")
    print(f"Mean composite score     : {agg['mean_score']}")
    print(f"Total wall time          : {agg['wall_seconds']} s")
    print("=" * 78)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the DevPilot AI evaluation benchmark.")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args()

    result = run_benchmark()
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_table(result)


if __name__ == "__main__":
    main()
