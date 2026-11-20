"""Database engine/session. Lazy so the app (and tests) start without Postgres.

TODO(Basit): switch routers from fixtures to real DB sessions.
"""
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False)
    return _engine


def get_db() -> Iterator[Session]:
    get_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
