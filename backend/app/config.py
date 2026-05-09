"""Central configuration for DevPilot AI.

Three run modes drive the whole system:

- ``mock``  : no LLM, no external services required. Deterministic agents that do
              real file ops, real git diffs and real test runs. Best for demos/CI.
- ``local`` : uses Ollama (http://localhost:11434) with a local code model.
- ``api``   : uses a hosted provider (OpenAI / Anthropic / Gemini) if a key is set.

Everything degrades gracefully: if Postgres/pgvector is unavailable we use SQLite
with an in-process numpy vector index; if sentence-transformers is missing we use
deterministic feature-hash embeddings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "backend" / ".devpilot_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACES_DIR = DATA_DIR / "workspaces"
WORKSPACES_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DEVPILOT_", extra="ignore")

    # --- run mode ---
    mode: Literal["mock", "local", "api"] = "mock"

    # --- database ---
    # If unset, we fall back to a local SQLite file (zero-config path).
    database_url: str = ""
    sqlite_path: str = str(DATA_DIR / "devpilot.db")

    # --- redis (optional) ---
    redis_url: str = ""

    # --- llm ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    api_model: str = "gpt-4o-mini"

    # --- embeddings ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384  # MiniLM dim; deterministic fallback uses the same dim

    # --- rag / retrieval ---
    top_k: int = 8
    hybrid_alpha: float = 0.5  # weight on dense vs sparse (0=BM25 only, 1=vector only)
    max_chunk_lines: int = 60
    chunk_overlap_lines: int = 8

    # --- agents ---
    max_repair_iterations: int = 3
    require_plan_approval: bool = False  # auto-approve in mock for one-shot demos
    sandbox_timeout_seconds: int = 120

    # --- server ---
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.sqlite_path}"

    @property
    def using_postgres(self) -> bool:
        return self.effective_database_url.startswith("postgresql")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
