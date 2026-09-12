"""Engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base


def _engine_kwargs() -> dict:
    if settings.database_url.startswith("sqlite"):
        # SQLite needs this to be usable from FastAPI's threadpool.
        return {"connect_args": {"check_same_thread": False}}
    # Postgres on a serverless host: recycle aggressively because idle
    # connections get dropped by the pooler.
    return {"pool_pre_ping": True, "pool_recycle": 280, "pool_size": 5}


engine = create_engine(settings.database_url, future=True, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables. Alembic owns this in production; used for dev and tests."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a transactional session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
