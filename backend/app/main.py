import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services.storage_service import get_storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # uvicorn이 포트를 연 직후 실행 — DB 연결 실패해도 앱은 기동 유지
    get_storage()
    for path in [settings.images_path, settings.chroma_path,
                 settings.documents_path, settings.markdowns_path]:
        os.makedirs(path, exist_ok=True)
    try:
        from app.database import create_tables  # lazy import — psycopg2 이 시점에 로딩
        create_tables()
        logger.info("DB 테이블 초기화 완료")
    except Exception as exc:
        logger.error("DB 테이블 초기화 실패 (앱은 계속 실행): %s", exc)

    reset_pw = os.environ.get("ADMIN_PASSWORD_RESET", "")
    if reset_pw:
        try:
            from app.database import _get_session_local
            from app.models.db_models import User
            from app.security.jwt_handler import hash_password
            db = _get_session_local()()
            admin = db.query(User).filter(User.is_admin == True).first()  # noqa: E712
            if admin:
                admin.hashed_password = hash_password(reset_pw)
                db.commit()
                logger.info("관리자 비밀번호 리셋 완료 (ADMIN_PASSWORD_RESET)")
            db.close()
        except Exception as exc:
            logger.error("관리자 비밀번호 리셋 실패: %s", exc)

    yield


app = FastAPI(
    title="무선통신프로토콜 위키백과사전 에이전트",
    description="LGU+ 기술규격서 기반 RAG 검색 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
from app.api import admin_users, auth, chunks, documents, history, ingest, search, settings as settings_api  # noqa: E402

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chunks.router)
app.include_router(search.router)
app.include_router(history.router)
app.include_router(admin_users.router)
app.include_router(ingest.router)
app.include_router(settings_api.router)

# 이미지 정적 파일 서빙
os.makedirs(settings.images_path, exist_ok=True)
app.mount("/images", StaticFiles(directory=settings.images_path), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
