"""DevPilot AI — FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload --port 8000
Health check:  curl http://localhost:8000/api/health
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_routes, chat_routes, metrics_routes, repo_routes
from app.config import settings
from app.db.session import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("devpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info(
        "DevPilot AI started | mode=%s | db=%s",
        settings.mode,
        "postgres" if settings.using_postgres else "sqlite",
    )
    yield


app = FastAPI(
    title="DevPilot AI",
    description=(
        "Local-first multi-agent engineering operating system: RAG + LangGraph "
        "agents + MCP tools + sandboxed tests + observability."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repo_routes.router)
app.include_router(chat_routes.router)
app.include_router(agent_routes.router)
app.include_router(metrics_routes.router)


@app.get("/")
def root():
    return {
        "name": "DevPilot AI",
        "version": "1.0.0",
        "mode": settings.mode,
        "docs": "/docs",
        "health": "/api/health",
    }
