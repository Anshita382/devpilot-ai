# Evaluation

The evaluation harness (`backend/eval/run_eval.py`) runs the full agent pipeline
over a fixed benchmark of seven tasks — one per supported intent plus a generic
catch-all — against the bundled sample FastAPI repo, and reports aggregate
metrics.

```bash
make eval                     # human-readable table
cd backend && python -m eval.run_eval --json   # machine-readable
```

## Metrics

| Metric | Definition |
|--------|------------|
| **Task completion rate** | Fraction of runs where tests passed *and* the reviewer approved |
| **Test-pass rate** | Mean fraction of test runs that passed |
| **Retrieval precision@k** | Fraction of top-k retrieved chunks from the anchor file, measured pre-edit |
| **Repair iterations** | Mean self-healing retries needed |
| **Latency / task** | Mean wall-clock per run |
| **Tool-call success rate** | Fraction of MCP tool invocations that succeeded |
| **Composite score** | `0.5·completed + 0.2·test_pass + 0.2·precision + 0.1·tool_success` |

## Reference run (mock mode)

These are the actual numbers printed by the harness on the sample repo:

```
Tasks evaluated           : 7
Task completion rate      : 100.0%
Mean test-pass rate       : 100.0%
Mean retrieval precision@k:  28.6%
Mean repair iterations    :  0
Mean latency / task       : ~1.2 s
Mean tool-call success    : 100.0%
Mean composite score      :  0.857
```

## Interpreting the numbers honestly

- **Repair iterations = 0** in mock mode is expected: the deterministic coder
  emits a self-consistent passing test on the first try. The self-healing loop is
  therefore validated in the *test suite* instead, with an injected flaky tester
  (`test_self_healing_retries_then_passes`) and an always-failing tester that
  proves the iteration cap (`test_max_iterations_cap`).
- **Precision@k = 28.6%** is a function of the tiny sample repo (≈2 of 8 retrieved
  chunks land in the single anchor file). Against a larger real codebase this
  number is more representative. Crucially it's measured on the clean workspace
  before the coder writes its files, so it reflects retrieval quality rather than
  the agent's own additions.
- The harness is **reproducible**: deterministic embeddings and deterministic mock
  agents mean the same inputs produce the same scores every run, so the README can
  quote measured figures rather than aspirational ones.

## Extending the benchmark

Add tasks to the `TASKS` list in `run_eval.py`, or point `SAMPLE_REPO` at a larger
repository to measure retrieval and latency on realistic code. In `local`/`api`
mode the same harness measures a real model's behaviour through the identical
pipeline.
