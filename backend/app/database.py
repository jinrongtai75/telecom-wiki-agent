from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# SQLite는 check_same_thread 필요, PostgreSQL은 불필요
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# PostgreSQL URL을 psycopg2 드라이버로 명시 (postgresql:// → postgresql+psycopg2://)
_db_url = settings.database_url
if _db_url.startswith("postgresql://") or _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)

engine = create_engine(_db_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from app.models import db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
