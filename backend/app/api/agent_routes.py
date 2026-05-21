"""Agent workflow routes.

Runs are executed synchronously inside the request for one-shot runnability
(no Celery/Redis broker required). The design keeps a clean seam so the call
can be moved behind a task queue later: ``run_agent_workflow`` is already a
pure ``(db, run) -> state`` function.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.agents.graph import run_agent_workflow
from app.config import settings
from app.db.models import AgentRun, AgentStep, Evaluation, Patch, Repository, TestRun
from app.db.session import SessionLocal, get_db
from app.schemas.repo import RunDetail, RunOut, StepOut

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/run", response_model=RunDetail)
def run_agent(req: "RunRequestBody", db: Session = Depends(get_db)):
    repo = db.get(Repository, req.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="repo not found")

    run = AgentRun(repo_id=req.repo_id, user_task=req.task, mode=settings.mode, status="created")
    db.add(run)
    db.flush()

    if settings.require_plan_approval:
        # Stop after planning; caller approves via /approve-plan to continue.
        from app.agents.planner import plan as make_plan

        repo_summary = {
            "name": repo.name,
            "language": repo.language,
            "n_files": repo.n_files,
            "entrypoint": "app/main.py",
        }
        state = {"repo_id": repo.id, "user_task": req.task, "mode": settings.mode}
        plan = make_plan(state, repo_summary)
        run.plan_json = json.dumps(plan)
        run.status = "awaiting_approval"
        db.commit()
        return _detail(db, run.id)

    run_agent_workflow(db, run)
    db.commit()
    return _detail(db, run.id)


@router.post("/{run_id}/approve-plan", response_model=RunDetail)
def approve_plan(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status not in ("awaiting_approval", "created"):
        raise HTTPException(status_code=409, detail=f"run is '{run.status}', cannot approve")
    run_agent_workflow(db, run)
    db.commit()
    return _detail(db, run.id)


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return _detail(db, run_id)


@router.get("/{run_id}/patch", response_class=PlainTextResponse)
def get_patch(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    patch = (
        db.query(Patch).filter(Patch.run_id == run_id).order_by(Patch.id.desc()).first()
    )
    return PlainTextResponse(patch.diff_text if patch else run.patch_text or "")


@router.get("/{run_id}/events")
def stream_events(run_id: int):
    """Replay recorded steps as Server-Sent Events.

    Because runs complete synchronously, this streams the already-persisted step
    timeline — enough to drive a live-looking UI without a message broker.
    """

    def gen():
        db = SessionLocal()
        try:
            run = db.get(AgentRun, run_id)
            if not run:
                yield _sse({"type": "error", "message": "run not found"})
                return
            steps = (
                db.query(AgentStep)
                .filter(AgentStep.run_id == run_id)
                .order_by(AgentStep.seq)
                .all()
            )
            for s in steps:
                yield _sse(
                    {
                        "type": "step",
                        "seq": s.seq,
                        "agent": s.agent,
                        "status": s.status,
                        "message": s.message,
                        "latency_ms": s.latency_ms,
                    }
                )
            yield _sse({"type": "done", "status": run.status})
        finally:
            db.close()

    return StreamingResponse(gen(), media_type="text/event-stream")


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _detail(db: Session, run_id: int) -> RunDetail:
    run = db.get(AgentRun, run_id)
    steps = (
        db.query(AgentStep).filter(AgentStep.run_id == run_id).order_by(AgentStep.seq).all()
    )
    test_runs = (
        db.query(TestRun).filter(TestRun.run_id == run_id).order_by(TestRun.id).all()
    )
    evaluation = db.query(Evaluation).filter(Evaluation.run_id == run_id).first()
    patch = (
        db.query(Patch).filter(Patch.run_id == run_id).order_by(Patch.id.desc()).first()
    )

    plan = json.loads(run.plan_json or "{}")
    retrieved: list[dict] = []
    for s in steps:
        if s.agent == "retrieval":
            try:
                payload = json.loads(s.payload_json or "{}")
                retrieved = payload.get("retrieved", [])
            except json.JSONDecodeError:
                retrieved = []

    return RunDetail(
        run=RunOut.model_validate(run),
        plan=plan,
        steps=[
            StepOut(
                seq=s.seq,
                agent=s.agent,
                status=s.status,
                message=s.message,
                latency_ms=s.latency_ms,
            )
            for s in steps
        ],
        retrieved=retrieved,
        test_runs=[
            {
                "command": t.command,
                "passed": t.passed,
                "total_tests": t.total_tests,
                "failed_tests": t.failed_tests,
                "iteration": t.iteration,
                "logs": t.logs[-4000:],
            }
            for t in test_runs
        ],
        diff=(patch.diff_text if patch else run.patch_text) or "",
        pr_summary=run.pr_summary or "",
        evaluation=json.loads(evaluation.report_json) if evaluation else {},
    )


# Local import to avoid a circular reference in schemas typing.
from app.schemas.repo import RunRequest as RunRequestBody  # noqa: E402
