import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import documents, objects, settings

app = FastAPI(title="Doc Preprocessing Tool", version="1.0.0")

_default_origins = ",".join([
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:1024",
    "https://telecom-wiki-agent-kbbr.vercel.app",
    "https://telecom-wiki-agent.vercel.app",
])
_cors_origins = os.environ.get("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(objects.router)
app.include_router(settings.router)

# 이미지 정적 파일 서빙
images_dir = Path(__file__).parent.parent / "images"
images_dir.mkdir(exist_ok=True)
app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
