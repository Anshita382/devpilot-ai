"""Repo Q&A routes — hybrid RAG retrieval with a grounded answer.

In ``mock`` mode we synthesise a deterministic, citation-style answer from the
retrieved chunks (no LLM required). In ``local``/``api`` mode we pass the same
retrieved context to the configured model.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Repository
from app.db.session import get_db
from app.llm.client import LLMUnavailable, complete
from app.llm import prompts
from app.rag.retriever import retrieve
from app.schemas.repo import ChatRequest, ChatResponse, RetrievedChunkOut

router = APIRouter(prefix="/api/repos", tags=["chat"])


def _mock_answer(query: str, chunks: list) -> str:
    if not chunks:
        return (
            "I couldn't find anything relevant in the indexed code for that "
            "question. Try ingesting the repository first, or rephrase the query."
        )
    files = []
    for c in chunks[:5]:
        loc = f"{c.file_path}:{c.start_line}-{c.end_line}"
        label = c.symbol or c.kind
        files.append(f"- `{loc}` ({label})")
    top = chunks[0]
    return (
        f"Based on hybrid retrieval over the repository, the most relevant code "
        f"for **\"{query}\"** is in `{top.file_path}` "
        f"(symbol `{top.symbol or top.kind}`, lines {top.start_line}-{top.end_line}).\n\n"
        f"Supporting locations:\n" + "\n".join(files) + "\n\n"
        f"Top match preview:\n```\n{top.text[:400]}\n```"
    )


@router.post("/{repo_id}/chat", response_model=ChatResponse)
def chat(repo_id: int, req: ChatRequest, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="repo not found")

    chunks = retrieve(db, repo_id, req.query, top_k=req.top_k or settings.top_k)

    if settings.mode == "mock":
        answer = _mock_answer(req.query, chunks)
    else:
        context = "\n\n".join(
            f"### {c.file_path}:{c.start_line}-{c.end_line} ({c.symbol or c.kind})\n{c.text}"
            for c in chunks
        )
        user_msg = (
            f"Repository: {repo.name}\n\nRetrieved context:\n{context}\n\n"
            f"Question: {req.query}\n\nAnswer using only the retrieved context."
        )
        try:
            answer = complete(prompts.RETRIEVAL, user_msg)
        except LLMUnavailable:
            answer = _mock_answer(req.query, chunks)

    out_chunks = [
        RetrievedChunkOut(
            file_path=c.file_path,
            symbol=c.symbol,
            kind=c.kind,
            start_line=c.start_line,
            end_line=c.end_line,
            score=round(c.score, 4),
            preview=c.text[:300],
        )
        for c in chunks
    ]
    return ChatResponse(answer=answer, chunks=out_chunks)
