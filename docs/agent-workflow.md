# Agent Workflow

Each run moves a shared `AgentState` through six nodes. This document describes
what each one does and how the self-healing loop works.

## State

`AgentState` (a `total=False` TypedDict) carries inputs (`run_id`, `repo_id`,
`user_task`, `mode`, `workspace`), then accumulates plan, retrieved context,
diff, test results, review, and evaluation as it flows through the graph.

## Nodes

### 1. Planner
Classifies the task into an intent (`health`, `cache`, `validation`,
`pagination`, `logging`, `error_handling`, or `generic`) and emits a structured
plan: a summary, ordered subtasks, target files, a risk level, and the tools it
expects to use. In `local`/`api` mode the LLM produces the plan and the
deterministic plan is the fallback.

### 2. Retrieval
Runs hybrid retrieval (see `rag-design.md`) using the plan summary, intent, and
target files as the query. It also computes **retrieval precision@k right here**,
on the clean workspace before any code is written, and stashes it in state — this
prevents the agent's own newly-created files from contaminating the metric.

### 3. Coder
Applies the change through the MCP tool registry and returns the real `git diff`.

- **mock**: a deterministic per-intent "skill" writes a real feature module plus a
  self-consistent passing unit test into a `devpilot_changes/` package at the
  workspace root.
- **local/api**: the LLM authors the module body; the output is compile-checked,
  and if it's unusable the deterministic skill is used instead — so a runnable
  patch is always produced.

### 4. Tester
Detects the project type and runs its test command in the sandbox, parsing the
output into `(passed, total, failed)`. Each run is persisted as a `TestRun` with
its iteration number.

### 5. Reviewer
Heuristic review flags risky patterns (`eval`/`exec`, `shell=True`, hardcoded
secrets, disabled TLS verification), checks that tests exist and pass, and weighs
diff size. In non-mock modes an LLM review augments the heuristics.

### 6. Evaluator
Computes a weighted composite score from task completion, test pass rate,
retrieval precision@k, and tool-call success rate, then drafts a markdown PR
summary.

## The self-healing loop

After the Tester, a conditional edge calls `_route_after_test`:

```python
if state["test_passed"] or state["iteration"] >= state["max_iterations"]:
    return "reviewer"   # done — success, or out of repair budget
return "coder"          # retry: loop back and try again
```

`max_iterations` comes from `DEVPILOT_MAX_REPAIR_ITERATIONS` (default 3). This is
verified by two tests that inject a flaky tester: one that fails once then passes
(asserts the Coder runs ≥2 times), and one that always fails (asserts the loop
stops exactly at the cap and the run ends in `needs_review`).

## Plan approval (optional)

Set `DEVPILOT_REQUIRE_PLAN_APPROVAL=true` and `POST /api/agents/run` stops after
planning with status `awaiting_approval`; a follow-up
`POST /api/agents/{id}/approve-plan` runs the rest of the pipeline.
