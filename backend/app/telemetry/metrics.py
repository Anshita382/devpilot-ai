"""Prometheus metrics. Exposed at /api/metrics (and scraped by the bundled
Prometheus container in docker-compose)."""
from __future__ import annotations

from prometheus_client import Counter, Histogram

AGENT_RUNS = Counter("devpilot_agent_runs_total", "Agent runs by final status", ["status"])
AGENT_RUN_LATENCY = Histogram("devpilot_agent_run_latency_seconds", "End-to-end agent run latency")
AGENT_STEP_LATENCY = Histogram("devpilot_agent_step_latency_seconds", "Per-agent step latency", ["agent"])
TEST_PASS = Counter("devpilot_test_runs_total", "Test runs by pass/fail", ["passed"])
REPO_INGESTS = Counter("devpilot_repo_ingests_total", "Repositories ingested")
TOOL_CALLS = Counter("devpilot_tool_calls_total", "MCP tool calls", ["tool", "success"])
