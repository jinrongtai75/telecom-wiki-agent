from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# engine / SessionLocal은 최초 DB 접근 시 생성 (lazy)
# — create_engine() 자체가 psycopg2를 import하므로
#   모듈 로드 시점이 아닌 lifespan 이후로 미룸
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        is_sqlite = url.startswith("sqlite")
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        connect_args = {"check_same_thread": False} if is_sqlite else {"connect_timeout": 10}
        _engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        logger.info("DB engine created: %s", url.split("@")[-1] if "@" in url else url)
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


class Base(DeclarativeBase):
    pass


def get_db():
    db = _get_session_local()()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from app.models import db_models  # noqa: F401
    Base.metadata.create_all(bind=_get_engine())
