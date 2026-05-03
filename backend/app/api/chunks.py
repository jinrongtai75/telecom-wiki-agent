"""
청크 CRUD + VLM 검수 API.
ParsedChunkDB의 수정/삭제/재정렬 및 VLM 호출 엔드포인트.
"""
from __future__ import annotations

import base64
import json
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.db_models import AppSetting, ParsedChunkDB, User
from app.models.schemas import (
    ChatEditRequest,
    ChunkInfo,
    ChunkUpdateRequest,
    ReorderRequest,
    VlmRequest,
)
from app.modules.llm_client import LLMClient
from app.security.auth_deps import require_admin


def _get_llm(api_token: str, db: Session) -> LLMClient:
    token = api_token or os.environ.get("GEMINI_API_KEY", "")
    if not token:
        setting = db.get(AppSetting, "gemini_token")
        if setting and setting.value:
            token = setting.value
    return LLMClient(api_token=token)

router = APIRouter(prefix="/api/chunks", tags=["chunks"])

TABLE_REVIEW_PROMPT = """다음 마크다운 표를 분석하고 JSON으로만 응답하세요:

{"action": "keep|discard", "issues": "발견된 문제점", "processed_content": "수정된 표 (keep인 경우)"}

판단 기준:
- keep: 유효한 데이터 표
- discard: 파싱 오류, 의미 없는 표, 빈 표

JSON만 출력하세요.

표:
"""

TABLE_FLATTEN_PROMPT = """다음 마크다운 표를 plain text로 변환하세요.
각 행의 내용을 "항목명: 값" 형식으로 나열하세요.
표 구조 기호(|, --)는 제거하세요.
변환된 텍스트만 출력하세요.

표:
"""

IMAGE_REVIEW_PROMPT = """이 이미지를 분석하고 다음 JSON 형식으로만 응답하세요:

{"action": "discard|save|describe", "description": "이미지 설명", "result": "텍스트 변환 (describe인 경우)"}

판단 기준:
- discard: 의미 없는 이미지 (로고, 장식선, 빈 이미지)
- describe: 텍스트로 재현 가능 (표, 순서도, 다이어그램)
- save: 시각 정보가 필수 (그래프, 무선통신 신호, 측정 결과)

JSON만 출력하세요."""


def _chunk_to_info(c: ParsedChunkDB) -> ChunkInfo:
    return ChunkInfo(
        id=c.id,
        doc_id=c.doc_id,
        type=c.type,
        content=c.content,
        processed_content=c.processed_content,
        page=c.page,
        section=c.section,
        order=c.order,
        is_heading=c.is_heading,
        heading_level=c.heading_level,
        image_b64=c.image_b64,
        image_path=c.image_path,
        bbox_json=c.bbox_json,
        status=c.status,
    )


def _get_chunk_or_404(doc_id: str, chunk_id: str, db: Session) -> ParsedChunkDB:
    c = db.query(ParsedChunkDB).filter(
        ParsedChunkDB.doc_id == doc_id, ParsedChunkDB.id == chunk_id
    ).first()
    if not c:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
    return c


def _parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


@router.get("/{doc_id}", response_model=list[ChunkInfo])
def get_chunks(
    doc_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """문서의 모든 청크를 order 순으로 반환."""
    chunks = (
        db.query(ParsedChunkDB)
        .filter(ParsedChunkDB.doc_id == doc_id)
        .order_by(ParsedChunkDB.order)
        .all()
    )
    return [_chunk_to_info(c) for c in chunks]


@router.put("/{doc_id}/{chunk_id}", response_model=ChunkInfo)
def update_chunk(
    doc_id: str,
    chunk_id: str,
    body: ChunkUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    if body.content is not None:
        c.content = body.content
    if body.processed_content is not None:
        c.processed_content = body.processed_content
    if body.is_heading is not None:
        c.is_heading = body.is_heading
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


@router.delete("/{doc_id}/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chunk(
    doc_id: str,
    chunk_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    c.status = "discarded"
    db.commit()


@router.post("/{doc_id}/{chunk_id}/confirm", response_model=ChunkInfo)
def confirm_chunk(
    doc_id: str,
    chunk_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    c.status = "confirmed"
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


@router.post("/{doc_id}/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_chunks(
    doc_id: str,
    body: ReorderRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    for order, chunk_id in enumerate(body.ordered_ids):
        db.query(ParsedChunkDB).filter(
            ParsedChunkDB.doc_id == doc_id, ParsedChunkDB.id == chunk_id
        ).update({"order": order})
    db.commit()


# ── TABLE VLM ────────────────────────────────────────────────────────────────

@router.post("/{doc_id}/{chunk_id}/table/review", response_model=ChunkInfo)
def table_review(
    doc_id: str,
    chunk_id: str,
    body: VlmRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    effective = c.processed_content or c.content
    llm = _get_llm(body.api_token, db)
    try:
        raw = llm.complete(TABLE_REVIEW_PROMPT + effective)
        data = _parse_json_response(raw)
        if data.get("action") == "discard":
            c.status = "discarded"
        else:
            if data.get("processed_content"):
                c.processed_content = data["processed_content"]
            c.status = "confirmed"
    except Exception:
        pass
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


@router.post("/{doc_id}/{chunk_id}/table/flatten", response_model=ChunkInfo)
def table_flatten(
    doc_id: str,
    chunk_id: str,
    body: VlmRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    effective = c.processed_content or c.content
    llm = _get_llm(body.api_token, db)
    try:
        result = llm.complete(TABLE_FLATTEN_PROMPT + effective)
        c.processed_content = result.strip()
        c.type = "text"
    except Exception:
        pass
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


@router.post("/{doc_id}/{chunk_id}/table/chat", response_model=ChunkInfo)
def table_chat(
    doc_id: str,
    chunk_id: str,
    body: ChatEditRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    effective = c.processed_content or c.content
    llm = _get_llm(body.api_token, db)
    prompt = (
        f"다음 마크다운 표를 편집 요청에 따라 수정하세요. 수정된 표만 출력하세요.\n\n"
        f"표:\n{effective}\n\n요청: {body.message}"
    )
    try:
        result = llm.complete(prompt)
        c.processed_content = result.strip()
    except Exception:
        pass
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


# ── IMAGE VLM ────────────────────────────────────────────────────────────────

@router.post("/{doc_id}/{chunk_id}/image/review", response_model=ChunkInfo)
def image_review(
    doc_id: str,
    chunk_id: str,
    body: VlmRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    if not c.image_b64:
        raise HTTPException(status_code=400, detail="이미지 데이터 없음")

    llm = _get_llm(body.api_token, db)
    try:
        raw = llm.complete_with_image(IMAGE_REVIEW_PROMPT, c.image_b64)
        data = _parse_json_response(raw)
        action = data.get("action", "discard")

        if action == "discard":
            c.status = "discarded"
            c.image_b64 = None
        elif action == "describe":
            c.processed_content = data.get("result") or data.get("description", "")
            c.image_b64 = None
            c.status = "confirmed"
        elif action == "save":
            img_b64 = c.image_b64
            if img_b64.startswith("data:"):
                match = re.match(r"data:image/(\w+);base64,(.+)", img_b64, re.DOTALL)
                if match:
                    ext, raw_b64 = match.group(1), match.group(2)
                else:
                    ext, raw_b64 = "png", img_b64
            else:
                ext, raw_b64 = "png", img_b64
            filename = f"{doc_id}_p{c.page}_{uuid.uuid4().hex[:6]}.{ext}"
            filepath = os.path.join(settings.images_path, filename)
            with open(filepath, "wb") as fh:
                fh.write(base64.b64decode(raw_b64))
            c.image_path = f"/images/{filename}"
            c.processed_content = data.get("description", "")
            c.image_b64 = None
            c.status = "confirmed"
    except Exception:
        pass
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)


@router.post("/{doc_id}/{chunk_id}/image/chat", response_model=ChunkInfo)
def image_chat(
    doc_id: str,
    chunk_id: str,
    body: ChatEditRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = _get_chunk_or_404(doc_id, chunk_id, db)
    effective = c.processed_content or c.content or ""
    llm = _get_llm(body.api_token, db)
    prompt = (
        f"이미지 설명을 편집 요청에 따라 수정하세요. 수정된 설명만 출력하세요.\n\n"
        f"현재 설명:\n{effective}\n\n요청: {body.message}"
    )
    try:
        result = llm.complete(prompt)
        c.processed_content = result.strip()
    except Exception:
        pass
    db.commit()
    db.refresh(c)
    return _chunk_to_info(c)
