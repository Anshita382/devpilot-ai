"""Pydantic schemas for the API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class IngestRequest(BaseModel):
    url: str
    name: str | None = None


class RepoOut(BaseModel):
    id: int
    name: str
    url: str
    language: str
    status: str
    n_files: int
    n_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    query: str
    top_k: int | None = None


class RetrievedChunkOut(BaseModel):
    file_path: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    score: float
    preview: str


class ChatResponse(BaseModel):
    answer: str
    chunks: list[RetrievedChunkOut]


class RunRequest(BaseModel):
    repo_id: int
    task: str


class RunOut(BaseModel):
    id: int
    repo_id: int
    user_task: str
    status: str
    mode: str
    total_latency_ms: int
    total_retries: int

    class Config:
        from_attributes = True


class StepOut(BaseModel):
    seq: int
    agent: str
    status: str
    message: str
    latency_ms: int


class RunDetail(BaseModel):
    run: RunOut
    plan: dict
    steps: list[StepOut]
    retrieved: list[dict]
    test_runs: list[dict]
    diff: str
    pr_summary: str
    evaluation: dict
