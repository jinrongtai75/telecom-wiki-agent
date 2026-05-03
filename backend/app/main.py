import logging
import os
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.services.storage_service import get_storage

logger = logging.getLogger(__name__)

_reindex_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reindex")


def _run_auto_reindex() -> None:
    """Background thread: ChromaDB 소실 감지 → 자동 재인덱싱 (시작 지연 없음)."""
    try:
        from app.database import _get_session_local
        from app.models.db_models import Document
        from app.modules import vector_store
        from app.modules.md_chunker import md_chunker

        db = _get_session_local()()
        try:
            docs = db.query(Document).filter(Document.status == "indexed").all()
            if not docs:
                return

            collection = vector_store._get_collection()
            chroma_count = collection.count()
            db_count = sum(d.chunk_count or 0 for d in docs)

            if chroma_count >= db_count:
                logger.info("ChromaDB 정상 (chroma=%d, db=%d)", chroma_count, db_count)
                return

            logger.info("ChromaDB 소실 감지 (chroma=%d, db=%d) — 백그라운드 재인덱싱 시작", chroma_count, db_count)
            storage = get_storage()
            reindexed, errors = 0, 0
            for doc in docs:
                try:
                    if not doc.markdown_path:
                        continue
                    md_bytes = storage.load(doc.markdown_path)
                    vector_store.delete_doc(doc.id)
                    chunks = md_chunker.chunk_from_text(md_bytes.decode("utf-8"), doc.id)
                    count = vector_store.index_chunks(chunks)
                    doc.chunk_count = count
                    db.commit()
                    reindexed += 1
                    logger.info("재인덱싱 완료: %s (%d청크)", doc.original_name, count)
                except Exception as e:
                    errors += 1
                    logger.error("재인덱싱 실패: %s — %s", doc.original_name, e)
            logger.info("자동 재인덱싱 완료 — 성공: %d, 실패: %d", reindexed, errors)
        finally:
            db.close()
    except Exception as exc:
        logger.error("자동 재인덱싱 실패: %s", exc)


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

    # 임베딩 모델을 RAM에 미리 로드 — 첫 요청 타임아웃 방지
    try:
        from app.modules import vector_store
        vector_store._get_collection()
        logger.info("임베딩 모델 워밍업 완료")
    except Exception as exc:
        logger.error("임베딩 모델 워밍업 실패 (앱은 계속 실행): %s", exc)

    # Railway 재배포 시 ChromaDB 소실 → 백그라운드 스레드에서 자동 재인덱싱
    # (Gemini API 배치 호출이 길어서 healthcheck 타임아웃 방지를 위해 비동기 처리)
    _reindex_executor.submit(_run_auto_reindex)

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
