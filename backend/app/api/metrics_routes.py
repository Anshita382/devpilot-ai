"""Observability + health routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AgentRun, CodeChunk, Evaluation, Repository, ToolCall
from app.db.session import get_db

router = APIRouter(tags=["telemetry"])


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "mode": settings.mode,
        "database": "postgres" if settings.using_postgres else "sqlite",
        "repos": db.query(func.count(Repository.id)).scalar() or 0,
        "runs": db.query(func.count(AgentRun.id)).scalar() or 0,
    }


@router.get("/api/metrics")
def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/metrics/agent-runs")
def agent_run_metrics(db: Session = Depends(get_db)):
    """Aggregated JSON for the dashboard cards + recent runs table."""
    total_runs = db.query(func.count(AgentRun.id)).scalar() or 0
    completed = (
        db.query(func.count(AgentRun.id)).filter(AgentRun.status == "completed").scalar() or 0
    )
    avg_latency = db.query(func.avg(AgentRun.total_latency_ms)).scalar() or 0
    avg_retries = db.query(func.avg(AgentRun.total_retries)).scalar() or 0
    avg_score = db.query(func.avg(Evaluation.score)).scalar() or 0
    avg_precision = db.query(func.avg(Evaluation.retrieval_precision_at_k)).scalar() or 0
    avg_test_pass = db.query(func.avg(Evaluation.test_pass_rate)).scalar() or 0
    tool_calls = db.query(func.count(ToolCall.id)).scalar() or 0
    tool_success = (
        db.query(func.count(ToolCall.id)).filter(ToolCall.success.is_(True)).scalar() or 0
    )

    recent = (
        db.query(AgentRun).order_by(AgentRun.id.desc()).limit(10).all()
    )
    recent_rows = [
        {
            "id": r.id,
            "repo_id": r.repo_id,
            "task": r.user_task,
            "status": r.status,
            "latency_ms": r.total_latency_ms,
            "retries": r.total_retries,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in recent
    ]

    return {
        "repos_indexed": db.query(func.count(Repository.id)).scalar() or 0,
        "chunks_indexed": db.query(func.count(CodeChunk.id)).scalar() or 0,
        "total_runs": total_runs,
        "success_rate": round(completed / total_runs, 3) if total_runs else 0.0,
        "avg_latency_ms": int(avg_latency),
        "avg_retries": round(float(avg_retries), 2),
        "avg_score": round(float(avg_score), 3),
        "avg_precision_at_k": round(float(avg_precision), 3),
        "avg_test_pass_rate": round(float(avg_test_pass), 3),
        "tool_call_success_rate": round(tool_success / tool_calls, 3) if tool_calls else 0.0,
        "recent_runs": recent_rows,
    }
