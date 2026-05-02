"""Wiki Agent RAG 적재 프록시 — 자격증명은 서버 환경변수에서 관리."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.modules.api_key_manager import APIKeyManager

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

_WIKI_URL = os.environ.get("WIKI_AGENT_URL", "https://telecom-wiki-agent-production.up.railway.app")
_key_mgr = APIKeyManager()


def _get_wiki_user() -> str:
    return os.environ.get("WIKI_AGENT_USERNAME", "antonio")


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
            json={"username": _get_wiki_user(), "password": wiki_pass},
        )
        res.raise_for_status()
    return res.json()["access_token"]


@router.get("/check-wiki-auth")
async def check_wiki_auth():
    """Wiki Agent 로그인 진단용 엔드포인트 — 실제 로그인 시도 후 결과 반환."""
    import hashlib
    username = _get_wiki_user()
    wiki_pass = _get_wiki_pass()
    pass_from_env = os.environ.get("WIKI_AGENT_PASSWORD", "")
    pass_from_mgr = _key_mgr.get_key("WIKI_AGENT_PASSWORD") or ""
    diag = {
        "env_var_len": len(pass_from_env),
        "env_var_stripped_len": len(pass_from_env.strip()),
        "env_var_sha256": hashlib.sha256(pass_from_env.encode()).hexdigest()[:12],
        "key_mgr_len": len(pass_from_mgr),
        "key_mgr_sha256": hashlib.sha256(pass_from_mgr.encode()).hexdigest()[:12],
        "final_pass_sha256": hashlib.sha256(wiki_pass.encode()).hexdigest()[:12] if wiki_pass else None,
    }
    if not wiki_pass:
        return {"ok": False, "username": username, "error": "비밀번호 미설정", "diag": diag}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                f"{_WIKI_URL}/api/auth/login",
                json={"username": username, "password": wiki_pass},
            )
        if res.status_code == 200:
            return {"ok": True, "username": username, "wiki_url": _WIKI_URL, "diag": diag}
        return {"ok": False, "username": username, "wiki_url": _WIKI_URL, "status": res.status_code, "detail": res.text[:200], "diag": diag}
    except Exception as e:
        return {"ok": False, "username": username, "error": str(e), "diag": diag}


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
        raise HTTPException(
            status_code=502,
            detail=f"Wiki Agent 로그인 실패 (username={_get_wiki_user()}, url={_WIKI_URL}, status={e.response.status_code}): {e.response.text[:200]}",
        ) from e

    files: dict = {}
    if pdf_file:
        pdf_bytes = await pdf_file.read()
        files["pdf_file"] = (pdf_file.filename, pdf_bytes, "application/pdf")

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            res = await client.post(
                f"{_WIKI_URL}/api/ingest/md",
                data={"filename": filename, "content": content, "source_name": source_name},
                files=files or None,
                headers={"Authorization": f"Bearer {token}"},
            )
            res.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Wiki Agent 적재 타임아웃 (300초 초과)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Wiki Agent 적재 실패 (status={e.response.status_code}): {e.response.text[:500]}",
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Wiki Agent 연결 오류: {e}") from e

    return JSONResponse(content=res.json())
