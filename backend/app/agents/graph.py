"""Agent workflow orchestrator.

Wires the six agents into a graph:

    planner -> retrieval -> coder -> tester --(fail & retries left)--> coder
                                          \\--(pass | out of retries)--> reviewer -> evaluator

Uses LangGraph's StateGraph when the package is importable; otherwise runs the
exact same node functions through a small manual executor so the system works
even if LangGraph is unavailable. Every node records an AgentStep with latency;
tool calls are logged live by the MCP registry.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents import coder, evaluator, planner, retrieval, reviewer, tester
from app.agents.state import AgentState
from app.config import settings
from app.db.models import AgentRun, AgentStep, Evaluation, Patch, TestRun, ToolCall
from app.mcp.server import ToolRegistry
from app.telemetry import metrics


class WorkflowRunner:
    def __init__(self, db: Session, run: AgentRun):
        self.db = db
        self.run = run
        self.repo = run.repo
        self.workspace = Path(self.repo.local_path)
        self.reg = ToolRegistry(self.workspace, db=db, run_id=run.id)
        self.events: list[dict] = []
        self.seq = 0
        self.repo_summary = {
            "name": self.repo.name,
            "language": self.repo.language,
            "n_files": self.repo.n_files,
            "entrypoint": self._guess_entrypoint(),
        }

    def _guess_entrypoint(self) -> str:
        for c in ["app/main.py", "main.py", "src/main.py", "app.py"]:
            if (self.workspace / c).exists():
                return c
        return "app/main.py"

    def _record(self, agent: str, message: str, payload: dict, latency_ms: int, status: str = "ok") -> None:
        self.seq += 1
        step = AgentStep(
            run_id=self.run.id,
            seq=self.seq,
            agent=agent,
            status=status,
            message=message,
            payload_json=json.dumps(payload)[:8000],
            latency_ms=latency_ms,
        )
        self.db.add(step)
        self.db.flush()
        self.events.append(
            {"seq": self.seq, "agent": agent, "status": status, "message": message, "latency_ms": latency_ms}
        )
        metrics.AGENT_STEP_LATENCY.labels(agent=agent).observe(latency_ms / 1000.0)

    # --- nodes ---------------------------------------------------------------
    def node_planner(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        self.reg.invoke("summarize_repo")  # exercise a tool + log it
        plan = planner.plan(state, self.repo_summary)
        lat = int((time.perf_counter() - t0) * 1000)
        self._record("planner", f"Planned intent '{plan.get('intent')}' ({len(plan.get('subtasks', []))} subtasks)", plan, lat)
        return {"plan": plan, "approved": not settings.require_plan_approval}

    def node_retrieval(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        payload, summary = retrieval.retrieve_context(self.db, state)
        lat = int((time.perf_counter() - t0) * 1000)
        # Measure retrieval precision now, on the clean workspace, before the
        # coder writes any new files (which would otherwise contaminate it).
        precision = evaluator.precision_at_retrieval(
            payload, state.get("plan", {}), state["workspace"]
        )
        self._record("retrieval", summary, {"retrieved": payload, "precision_at_k": precision}, lat)
        return {"retrieved": payload, "retrieval_summary": summary, "retrieval_precision": precision}

    def node_coder(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        result = coder.apply_changes(state, self.reg)
        lat = int((time.perf_counter() - t0) * 1000)
        iteration = state.get("iteration", 0) + 1
        self._record(
            "coder",
            f"Applied changes to {result['files_changed']} file(s) (iteration {iteration})",
            {k: v for k, v in result.items() if k != "diff"},
            lat,
        )
        return {**result, "iteration": iteration}

    def node_tester(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        res = tester.run(state)
        lat = int((time.perf_counter() - t0) * 1000)
        self.db.add(
            TestRun(
                run_id=self.run.id,
                command=res["command"],
                passed=res["passed"],
                total_tests=res["total"],
                failed_tests=res["failed"],
                logs=res["logs"],
                iteration=state.get("iteration", 1),
            )
        )
        self.db.flush()
        status = "ok" if res["passed"] else "fail"
        self._record("tester", f"{res['command']}: {'PASS' if res['passed'] else 'FAIL'} "
                                f"({res['total']} tests, {res['failed']} failed)",
                     {k: v for k, v in res.items() if k != "logs"}, lat, status)
        metrics.TEST_PASS.labels(passed=str(res["passed"]).lower()).inc()
        return {
            "test_passed": res["passed"],
            "test_total": res["total"],
            "test_failed": res["failed"],
            "test_logs": res["logs"],
        }

    def node_reviewer(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        rev = reviewer.review(state)
        lat = int((time.perf_counter() - t0) * 1000)
        self._record("reviewer", f"approved={rev['approved']} "
                                 f"({len(rev['issues'])} issues, {len(rev['suggestions'])} suggestions)",
                     rev, lat, "ok" if rev["approved"] else "warn")
        return {"review": rev}

    def node_evaluator(self, state: AgentState) -> dict:
        t0 = time.perf_counter()
        tool_calls = self.db.query(ToolCall).filter(ToolCall.run_id == self.run.id).all()
        tsr = (sum(1 for t in tool_calls if t.success) / len(tool_calls)) if tool_calls else 1.0
        total_latency = int((time.perf_counter() - self._start) * 1000)
        report = evaluator.evaluate(state, tsr, total_latency)
        summary = evaluator.pr_summary(state)
        lat = int((time.perf_counter() - t0) * 1000)
        self._record("evaluator", f"score={report['score']} completed={report['task_completed']}", report, lat)
        return {"evaluation": report, "pr_summary": summary}

    def _route_after_test(self, state: AgentState) -> str:
        if state.get("test_passed") or state.get("iteration", 1) >= state.get("max_iterations", 1):
            return "reviewer"
        return "coder"

    # --- execution -----------------------------------------------------------
    def _initial_state(self) -> AgentState:
        return AgentState(
            run_id=self.run.id,
            repo_id=self.repo.id,
            user_task=self.run.user_task,
            mode=settings.mode,
            workspace=str(self.workspace),
            iteration=0,
            max_iterations=settings.max_repair_iterations,
        )

    def execute(self) -> AgentState:
        self._start = time.perf_counter()
        self.reg.invoke("git_diff")  # establish git baseline before edits

        state = self._initial_state()
        try:
            state = self._run_langgraph(state)
        except Exception:
            state = self._run_manual(state)

        self._persist(state)
        return state

    def _run_langgraph(self, state: AgentState) -> AgentState:
        from langgraph.graph import END, StateGraph  # may raise -> manual fallback

        g = StateGraph(AgentState)
        g.add_node("planner", self.node_planner)
        g.add_node("retrieval", self.node_retrieval)
        g.add_node("coder", self.node_coder)
        g.add_node("tester", self.node_tester)
        g.add_node("reviewer", self.node_reviewer)
        g.add_node("evaluator", self.node_evaluator)

        g.set_entry_point("planner")
        g.add_edge("planner", "retrieval")
        g.add_edge("retrieval", "coder")
        g.add_edge("coder", "tester")
        g.add_conditional_edges("tester", self._route_after_test, {"coder": "coder", "reviewer": "reviewer"})
        g.add_edge("reviewer", "evaluator")
        g.add_edge("evaluator", END)

        compiled = g.compile()
        result = compiled.invoke(state, config={"recursion_limit": 50})
        return result  # type: ignore[return-value]

    def _run_manual(self, state: AgentState) -> AgentState:
        state.update(self.node_planner(state))
        state.update(self.node_retrieval(state))
        while True:
            state.update(self.node_coder(state))
            state.update(self.node_tester(state))
            if self._route_after_test(state) == "reviewer":
                break
        state.update(self.node_reviewer(state))
        state.update(self.node_evaluator(state))
        return state

    def _persist(self, state: AgentState) -> None:
        diff = state.get("diff", "")
        self.db.add(
            Patch(
                run_id=self.run.id,
                diff_text=diff,
                files_changed=state.get("files_changed", 0),
                insertions=state.get("insertions", 0),
                deletions=state.get("deletions", 0),
            )
        )
        report = state.get("evaluation", {})
        self.db.add(
            Evaluation(
                run_id=self.run.id,
                task_completed=report.get("task_completed", False),
                test_pass_rate=report.get("test_pass_rate", 0.0),
                retrieval_precision_at_k=report.get("retrieval_precision_at_k", 0.0),
                repair_iterations=report.get("repair_iterations", 0),
                latency_ms=report.get("latency_ms", 0),
                tool_success_rate=report.get("tool_success_rate", 0.0),
                score=report.get("score", 0.0),
                report_json=json.dumps(report),
            )
        )
        self.run.status = "completed" if report.get("task_completed") else "needs_review"
        self.run.plan_json = json.dumps(state.get("plan", {}))
        self.run.patch_text = diff
        self.run.pr_summary = state.get("pr_summary", "")
        self.run.total_latency_ms = report.get("latency_ms", 0)
        self.run.total_retries = report.get("repair_iterations", 0)
        self.run.completed_at = dt.datetime.now(dt.timezone.utc)
        self.db.flush()
        metrics.AGENT_RUNS.labels(status=self.run.status).inc()
        metrics.AGENT_RUN_LATENCY.observe(self.run.total_latency_ms / 1000.0)


def run_agent_workflow(db: Session, run: AgentRun) -> AgentState:
    run.status = "running"
    db.flush()
    runner = WorkflowRunner(db, run)
    return runner.execute()
