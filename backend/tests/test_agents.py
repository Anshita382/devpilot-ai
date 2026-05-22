"""Tests for the multi-agent workflow, including the self-healing loop."""
from app.agents import graph
from app.db.models import AgentRun, AgentStep
from app.rag.ingest import ingest_repo


def _ingest(db, sample_repo_path):
    repo = ingest_repo(db, "sample", sample_repo_path)
    db.commit()
    return repo


def test_full_workflow_completes(db, sample_repo_path):
    repo = _ingest(db, sample_repo_path)
    run = AgentRun(repo_id=repo.id, user_task="Add a health check endpoint", mode="mock")
    db.add(run)
    db.flush()

    state = graph.run_agent_workflow(db, run)
    db.commit()

    assert run.status == "completed"
    report = state["evaluation"]
    assert report["task_completed"] is True
    assert report["test_pass_rate"] == 1.0
    assert state["diff"].strip(), "expected a non-empty diff"

    # All six agents should have recorded at least one step.
    agents_seen = {s.agent for s in db.query(AgentStep).filter(AgentStep.run_id == run.id)}
    assert {"planner", "retrieval", "coder", "tester", "reviewer", "evaluator"} <= agents_seen


def test_self_healing_retries_then_passes(db, sample_repo_path, monkeypatch):
    """First test run fails, second passes — the loop must retry the coder."""
    repo = _ingest(db, sample_repo_path)
    run = AgentRun(repo_id=repo.id, user_task="Add input validation", mode="mock")
    db.add(run)
    db.flush()

    calls = {"n": 0}
    real_run = graph.tester.run

    def flaky_tester(state):
        calls["n"] += 1
        result = real_run(state)
        if calls["n"] == 1:
            # Force a failure on the first attempt.
            return {**result, "passed": False, "failed": 1, "total": max(result["total"], 1)}
        return result

    monkeypatch.setattr(graph.tester, "run", flaky_tester)

    state = graph.run_agent_workflow(db, run)
    db.commit()

    assert calls["n"] >= 2, "tester should have run more than once"
    coder_steps = [s for s in db.query(AgentStep).filter(AgentStep.run_id == run.id) if s.agent == "coder"]
    assert len(coder_steps) >= 2, "coder should have retried after the failure"
    assert state["iteration"] >= 2


def test_max_iterations_cap(db, sample_repo_path, monkeypatch):
    """If tests never pass, the loop must stop at max_repair_iterations."""
    repo = _ingest(db, sample_repo_path)
    run = AgentRun(repo_id=repo.id, user_task="Add a cache layer", mode="mock")
    db.add(run)
    db.flush()

    real_run = graph.tester.run

    def always_fail(state):
        result = real_run(state)
        return {**result, "passed": False, "failed": 1, "total": max(result["total"], 1)}

    monkeypatch.setattr(graph.tester, "run", always_fail)

    from app.config import settings

    graph.run_agent_workflow(db, run)
    db.commit()

    coder_steps = [s for s in db.query(AgentStep).filter(AgentStep.run_id == run.id) if s.agent == "coder"]
    assert len(coder_steps) == settings.max_repair_iterations
    assert run.status == "needs_review"
