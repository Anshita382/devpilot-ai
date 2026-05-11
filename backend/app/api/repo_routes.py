"""Repository routes: ingest, list, detail."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Repository
from app.db.session import get_db
from app.rag.ingest import ingest_repo
from app.schemas.repo import IngestRequest, RepoOut
from app.telemetry import metrics

router = APIRouter(prefix="/api/repos", tags=["repos"])


def _derive_name(url: str) -> str:
    return url.rstrip("/").split("/")[-1].replace(".git", "") or "repo"


@router.post("/ingest", response_model=RepoOut)
def ingest(req: IngestRequest, db: Session = Depends(get_db)):
    name = req.name or _derive_name(req.url)
    try:
        repo = ingest_repo(db, name, req.url)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    metrics.REPO_INGESTS.inc()
    db.refresh(repo)
    return repo


@router.get("", response_model=list[RepoOut])
def list_repos(db: Session = Depends(get_db)):
    return db.query(Repository).order_by(Repository.id.desc()).all()


@router.get("/{repo_id}", response_model=RepoOut)
def get_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="repo not found")
    return repo
