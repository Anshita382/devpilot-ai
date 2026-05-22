"""API-level tests using FastAPI's TestClient end to end."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_env):
    # Rebuild the app against the isolated DB from tmp_env.
    import app.main as main

    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_root_and_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "DevPilot AI"

    h = client.get("/api/health")
    assert h.status_code == 200
    body = h.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"


def test_ingest_chat_and_run_flow(client, sample_repo_path):
    # Ingest the bundled sample repo (offline local path).
    ing = client.post("/api/repos/ingest", json={"url": sample_repo_path, "name": "sample"})
    assert ing.status_code == 200, ing.text
    repo = ing.json()
    assert repo["n_chunks"] > 0
    repo_id = repo["id"]

    # RAG chat returns grounded chunks.
    chat = client.post(f"/api/repos/{repo_id}/chat", json={"query": "how does product search work"})
    assert chat.status_code == 200
    assert chat.json()["chunks"], "expected retrieved chunks"

    # Run the agent workflow.
    run = client.post("/api/agents/run", json={"repo_id": repo_id, "task": "Add a health check endpoint"})
    assert run.status_code == 200, run.text
    detail = run.json()
    assert detail["run"]["status"] == "completed"
    assert detail["diff"].strip()
    assert detail["evaluation"]["task_completed"] is True

    # Patch endpoint returns the diff text.
    run_id = detail["run"]["id"]
    patch = client.get(f"/api/agents/{run_id}/patch")
    assert patch.status_code == 200
    assert "diff --git" in patch.text or patch.text.strip()

    # Dashboard metrics reflect the run.
    metrics = client.get("/api/metrics/agent-runs")
    assert metrics.status_code == 200
    assert metrics.json()["total_runs"] >= 1


def test_prometheus_endpoint(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert "devpilot" in r.text or "agent" in r.text or r.text  # exposition text
