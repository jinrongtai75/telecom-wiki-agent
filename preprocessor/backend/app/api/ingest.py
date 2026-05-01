"""Wiki Agent RAG 적재 프록시 — 자격증명은 서버 환경변수에서 관리."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.modules.api_key_manager import APIKeyManager

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

_WIKI_URL = os.environ.get("WIKI_AGENT_URL", "https://telecom-wiki-agent-production.up.railway.app")
_WIKI_USER = os.environ.get("WIKI_AGENT_USERNAME", "antonio")
_key_mgr = APIKeyManager()


def _get_wiki_pass() -> str:
    return _key_mgr.get_key("WIKI_AGENT_PASSWORD") or os.environ.get("WIKI_AGENT_PASSWORD", "")


async def _get_wiki_token() -> str:
    wiki_pass = _get_wiki_pass()
    if not wiki_pass:
        raise HTTPException(
            status_code=503,
            detail="Wiki Agent 비밀번호가 설정되지 않았습니다. 설정 패널에서 입력해주세요.",
        )
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{_WIKI_URL}/api/auth/login",
            json={"username": _WIKI_USER, "password": wiki_pass},
        )
        res.raise_for_status()
    return res.json()["access_token"]


@router.post("/to-wiki")
async def ingest_to_wiki(
    filename: str = Form(...),
    content: str = Form(...),
    source_name: str = Form(...),
    pdf_file: UploadFile | None = File(None),
):
    if not _get_wiki_pass():
        raise HTTPException(status_code=503, detail="Wiki Agent 비밀번호가 설정되지 않았습니다. 설정 패널에서 입력해주세요.")

    try:
        token = await _get_wiki_token()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Wiki Agent 로그인 실패: {e.response.status_code}") from e

    files: dict = {}
    if pdf_file:
        pdf_bytes = await pdf_file.read()
        files["pdf_file"] = (pdf_file.filename, pdf_bytes, "application/pdf")

    async with httpx.AsyncClient(timeout=300) as client:
        res = await client.post(
            f"{_WIKI_URL}/api/ingest/md",
            data={"filename": filename, "content": content, "source_name": source_name},
            files=files or None,
            headers={"Authorization": f"Bearer {token}"},
        )
        res.raise_for_status()

    return JSONResponse(content=res.json())
