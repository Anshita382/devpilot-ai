# Architecture

DevPilot AI is a FastAPI backend, a Next.js frontend, and a set of supporting
services (Postgres+pgvector, Redis, Prometheus, Grafana) that are all optional in
the default configuration.

## Request paths

There are three primary flows:

1. **Ingestion** — `POST /api/repos/ingest` clones a Git URL (or copies a local
   path), walks source files, chunks them AST-aware, embeds the chunks, and
   persists everything. Embeddings are stored as JSON text so the same schema
   works on SQLite and Postgres; when Postgres+pgvector is present the vectors are
   mirrored into an `ivfflat` index for ANN search.

2. **Retrieval Q&A** — `POST /api/repos/{id}/chat` runs hybrid retrieval and, in
   non-mock modes, passes the retrieved context to the configured model. In mock
   mode it synthesises a deterministic, citation-style answer from the chunks.

3. **Agent workflow** — `POST /api/agents/run` executes the six-agent pipeline and
   persists every step, tool call, test run, patch, and evaluation.

## The agent graph

The workflow is a LangGraph `StateGraph` over a shared `AgentState` TypedDict.
Nodes are pure `state -> partial_state` functions wrapped by the runner, which
records an `AgentStep` and emits Prometheus timing for each.

```
planner → retrieval → coder → tester ──(pass | out of retries)──► reviewer → evaluator → END
                                  ▲                  │
                                  └──── (fail) ──────┘
```

If `langgraph` cannot be imported, a `_run_manual` executor reproduces the exact
same edges with a `while` loop, so the system never hard-depends on the graph
runtime.

## Persistence model

Nine tables (SQLAlchemy 2.0 `Mapped` style): `repositories`, `repo_files`,
`code_chunks`, `agent_runs`, `agent_steps`, `tool_calls`, `test_runs`, `patches`,
`evaluations`. The schema is identical across SQLite and Postgres; only the vector
search path differs.

## Tool layer (MCP)

The Coder never touches the filesystem directly — it goes through a tool registry
that mirrors the Model Context Protocol tool shape (name + JSON schema + handler).
Every invocation is logged as a `ToolCall` row with success/latency, which feeds
the tool-success-rate metric. Tools include `read_file`, `write_file`,
`list_files`, `search_code`, `git_diff`, `create_patch`, `apply_patch`,
`run_linter`, and `summarize_repo`, all with a workspace path-traversal guard. The
registry can also be served as a real stdio MCP server when the `mcp` package is
installed.

## Sandbox

The Tester detects the project type (Python/Node/Go/Maven) and runs the
appropriate test command. The default backend is `subprocess` scoped to the
workspace; setting `DEVPILOT_SANDBOX=docker` runs tests in a throwaway
`python:3.12-slim` container for stronger isolation.

## Observability

The backend exposes Prometheus metrics at `/api/metrics` (run counts by status,
run/step latency histograms, test pass/fail counters, tool-call counters,
ingestion counter). Prometheus scrapes the backend; Grafana auto-provisions a
datasource and a DevPilot dashboard. A JSON aggregate for the in-app dashboard is
served at `/api/metrics/agent-runs`.
