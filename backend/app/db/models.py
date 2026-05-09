"""SQLAlchemy models — the full schema from the design doc.

Tables: repositories, repo_files, code_chunks, agent_runs, agent_steps,
tool_calls, test_runs, patches, evaluations.

Embeddings are stored as JSON text so the schema is portable across SQLite and
Postgres. When running on Postgres the pgvector extension is enabled (see
``infra/postgres-init.sql``) and ``PgVectorStore`` can index the same vectors for
ANN search at scale; the default in-process numpy index needs no setup.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    local_path: Mapped[str] = mapped_column(String(1024), default="")
    language: Mapped[str] = mapped_column(String(64), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    n_files: Mapped[int] = mapped_column(Integer, default=0)
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    files: Mapped[list["RepoFile"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    chunks: Mapped[list["CodeChunk"]] = relationship(back_populates="repo", cascade="all, delete-orphan")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="repo", cascade="all, delete-orphan")


class RepoFile(Base):
    __tablename__ = "repo_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(1024))
    language: Mapped[str] = mapped_column(String(64), default="unknown")
    n_lines: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    repo: Mapped["Repository"] = relationship(back_populates="files")


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    symbol: Mapped[str] = mapped_column(String(255), default="")  # function/class name when known
    kind: Mapped[str] = mapped_column(String(32), default="block")  # function|class|block
    chunk_text: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer, default=0)
    end_line: Mapped[int] = mapped_column(Integer, default=0)
    embedding_json: Mapped[str] = mapped_column(Text, default="[]")

    repo: Mapped["Repository"] = relationship(back_populates="chunks")

    @property
    def embedding(self) -> list[float]:
        return json.loads(self.embedding_json or "[]")

    @embedding.setter
    def embedding(self, vec: list[float]) -> None:
        self.embedding_json = json.dumps([round(float(x), 6) for x in vec])


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    user_task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="created")
    mode: Mapped[str] = mapped_column(String(16), default="mock")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    patch_text: Mapped[str] = mapped_column(Text, default="")
    pr_summary: Mapped[str] = mapped_column(Text, default="")
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_retries: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    repo: Mapped["Repository"] = relationship(back_populates="runs")
    steps: Mapped[list["AgentStep"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    tool_calls: Mapped[list["ToolCall"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    test_runs: Mapped[list["TestRun"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="run", uselist=False, cascade="all, delete-orphan")


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    agent: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="ok")
    message: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["AgentRun"] = relationship(back_populates="steps")


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String(64))
    tool_input: Mapped[str] = mapped_column(Text, default="")
    tool_output: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["AgentRun"] = relationship(back_populates="tool_calls")


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    command: Mapped[str] = mapped_column(String(512))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    failed_tests: Mapped[int] = mapped_column(Integer, default=0)
    logs: Mapped[str] = mapped_column(Text, default="")
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["AgentRun"] = relationship(back_populates="test_runs")


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    diff_text: Mapped[str] = mapped_column(Text, default="")
    files_changed: Mapped[int] = mapped_column(Integer, default=0)
    insertions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    task_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    test_pass_rate: Mapped[float] = mapped_column(Float, default=0.0)
    retrieval_precision_at_k: Mapped[float] = mapped_column(Float, default=0.0)
    repair_iterations: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tool_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    report_json: Mapped[str] = mapped_column(Text, default="{}")

    run: Mapped["AgentRun"] = relationship(back_populates="evaluation")
