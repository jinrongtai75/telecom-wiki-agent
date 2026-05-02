"""
Google Gemini API 공통 클라이언트.
모든 LLM/VLM 호출은 이 모듈을 통해 처리한다.
"""
import json
import os

import httpx

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        from app.modules.api_key_manager import APIKeyManager  # noqa: PLC0415
        key = APIKeyManager().get_key("GEMINI") or ""
    return key


def call_llm(prompt: str, max_tokens: int = 1000) -> str:
    key = _get_api_key()
    if not key:
        raise RuntimeError("Gemini API 키가 설정되지 않았습니다. 설정 패널에서 입력하거나 GEMINI_API_KEY 환경변수를 설정하세요.")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    try:
        resp = httpx.post(f"{_GEMINI_URL}?key={key}", json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"LLM API 호출 실패 ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"LLM API 호출 실패: {e}")


def call_vlm(image_b64: str, prompt: str, max_tokens: int = 1000) -> str:
    """이미지 + 텍스트 VLM 호출.
    image_b64: 'data:image/png;base64,XXX' 형태의 data URI 또는 순수 base64 문자열 모두 허용.
    """
    key = _get_api_key()
    if not key:
        raise RuntimeError("Gemini API 키가 설정되지 않았습니다. 설정 패널에서 입력하거나 GEMINI_API_KEY 환경변수를 설정하세요.")

    if image_b64.startswith("data:"):
        header, raw_b64 = image_b64.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]
    else:
        raw_b64 = image_b64
        media_type = "image/png"

    body = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": raw_b64}},
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    try:
        resp = httpx.post(f"{_GEMINI_URL}?key={key}", json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"VLM API 호출 실패 ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"VLM API 호출 실패: {e}")
