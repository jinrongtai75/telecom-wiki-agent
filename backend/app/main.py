import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.services.storage_service import get_storage

app = FastAPI(
    title="무선통신프로토콜 위키백과사전 에이전트",
    description="LGU+ 기술규격서 기반 RAG 검색 API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 스토리지 초기화 (로컬이면 data/ 하위 디렉터리 자동 생성)
get_storage()

# 이미지·ChromaDB는 여전히 로컬 경로 사용
for path in [settings.images_path, settings.chroma_path]:
    os.makedirs(path, exist_ok=True)

# DB 테이블 생성
create_tables()

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
app.mount("/images", StaticFiles(directory=settings.images_path), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
