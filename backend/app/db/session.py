"""Engine + session management. Works with SQLite (default) or Postgres."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

_connect_args = {"check_same_thread": False} if settings.effective_database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.effective_database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db() -> None:
    """Create tables. On Postgres, also ensure the pgvector extension exists."""
    if settings.using_postgres:
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            # Extension may require superuser; numpy index still works regardless.
            pass
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
