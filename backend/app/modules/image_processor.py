"""
이미지 VLM 처리 모듈 — preprocessing-master image_processor.py 포팅.
VLM으로 이미지를 분석하여 discard/save/describe 판단.
"""
from __future__ import annotations

import base64
import json
import os
import uuid

from app.config import settings
from app.modules.llm_client import LLMClient
from app.modules.pdf_parser import ChunkType, ParsedChunk

REVIEW_PROMPT = """이 이미지를 분석하고 다음 JSON 형식으로만 응답하세요:

{"action": "discard|save|describe", "description": "이미지 설명", "result": "텍스트 변환 (describe인 경우)"}

판단 기준:
- discard: 의미 없는 이미지 (로고, 회사 CI, 장식선, 빈 이미지)
- describe: 텍스트로 재현 가능 (표, 순서도, 다이어그램, 텍스트 스크린샷)
- save: 시각 정보가 필수 (사진, 그래프, 무선통신 신호 다이어그램, 측정 결과 캡처)

JSON만 출력하고 다른 텍스트는 포함하지 마세요."""


def process_images(
    chunks: list[ParsedChunk],
    llm_client: LLMClient,
    doc_id: str,
) -> list[ParsedChunk]:
    """
    이미지 청크를 VLM으로 분석:
    - discard → 청크 제거
    - describe → content에 텍스트 설명 저장
    - save → 이미지 파일 저장 + image_path 메타데이터 기록
    """
    os.makedirs(settings.images_path, exist_ok=True)
    result: list[ParsedChunk] = []

    for chunk in chunks:
        if chunk.type != ChunkType.IMAGE:
            result.append(chunk)
            continue

        if not chunk.image_b64:
            # 이미지 데이터 없으면 버림
            continue

        try:
            action_data = _review_image(chunk.image_b64, llm_client)
            action = action_data.get("action", "discard")

            if action == "discard":
                continue  # 청크 제거

            elif action == "describe":
                chunk.content = action_data.get("result") or action_data.get("description", "")
                chunk.image_b64 = None  # 메모리 절약
                result.append(chunk)

            elif action == "save":
                # 이미지 파일로 저장
                image_path = _save_image(chunk.image_b64, doc_id, chunk.page)
                chunk.content = action_data.get("description", "")
                chunk.metadata["image_path"] = image_path
                chunk.image_b64 = None
                result.append(chunk)
            else:
                continue

        except Exception:
            # VLM 실패 시 이미지 청크 버림 (검색 품질 보호)
            continue

    return result


def _review_image(image_b64: str, llm_client: LLMClient) -> dict:
    """VLM으로 이미지 분석. JSON 반환."""
    text = llm_client.complete_with_image(REVIEW_PROMPT, image_b64)
    # JSON 추출 (마크다운 코드블록 제거)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "discard"}


def _save_image(image_b64: str, doc_id: str, page: int) -> str:
    """이미지를 파일로 저장하고 상대 경로 반환."""
    # data URI 접두어 처리
    if image_b64.startswith("data:"):
        import re
        match = re.match(r"data:image/(\w+);base64,(.+)", image_b64, re.DOTALL)
        if match:
            ext = match.group(1)
            raw_b64 = match.group(2)
        else:
            ext = "png"
            raw_b64 = image_b64
    else:
        ext = "png"
        raw_b64 = image_b64

    filename = f"{doc_id}_p{page}_{uuid.uuid4().hex[:6]}.{ext}"
    filepath = os.path.join(settings.images_path, filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(raw_b64))

    return f"/images/{filename}"
