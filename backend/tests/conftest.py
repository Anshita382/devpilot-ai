"""Shared pytest fixtures.

Every test runs against an isolated temporary SQLite DB and data directory so the
suite is fully self-contained and order-independent.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """Point DevPilot at an isolated SQLite DB for this test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DEVPILOT_MODE", "mock")
    monkeypatch.setenv("DEVPILOT_SQLITE_PATH", str(db_path))

    import app.config as config

    importlib.reload(config)
    import app.db.session as session

    importlib.reload(session)
    session.init_db()
    yield session
    session.engine.dispose()


@pytest.fixture()
def db(tmp_env):
    s = tmp_env.SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def sample_repo_path() -> str:
    here = Path(__file__).resolve().parents[2]
    return str(here / "examples" / "sample-fastapi-repo")
