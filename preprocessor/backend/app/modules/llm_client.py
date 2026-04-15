"""
JIHYE 게이트웨이 공통 클라이언트.
모든 LLM/VLM 호출은 이 모듈을 통해 처리한다.
api.anthropic.com / api.openai.com 직접 호출 금지.
"""
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"
_ENDPOINT = "https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6"


def _headers() -> dict:
    load_dotenv(_ENV_FILE, override=True)
    token = os.environ.get("JIHYE_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "bedrock-2023-05-31",
        "Content-Type": "application/json",
    }


def _parse_response(resp: httpx.Response) -> str:
    """outer.content → JSON 파싱 → inner.content[0].text 추출"""
    resp.raise_for_status()
    outer = resp.json()
    inner = json.loads(outer["content"])
    return inner["content"][0]["text"].strip()


def call_llm(prompt: str, max_tokens: int = 1000) -> str:
    """텍스트 전용 LLM 호출"""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        resp = httpx.post(_ENDPOINT, headers=_headers(), json=body, timeout=60)
        return _parse_response(resp)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"LLM API 호출 실패 ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"LLM API 호출 실패: {e}")


def call_vlm(image_b64: str, prompt: str, max_tokens: int = 1000) -> str:
    """이미지 + 텍스트 VLM 호출.
    image_b64: 'data:image/png;base64,XXX' 형태의 data URI 또는 순수 base64 문자열 모두 허용.
    """
    # data URI 접두어 제거 후 media_type 추출
    if image_b64.startswith("data:"):
        header, raw_b64 = image_b64.split(",", 1)
        media_type = header.split(":")[1].split(";")[0]  # e.g. "image/png"
    else:
        raw_b64 = image_b64
        media_type = "image/png"

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": raw_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    try:
        resp = httpx.post(_ENDPOINT, headers=_headers(), json=body, timeout=60)
        return _parse_response(resp)
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"VLM API 호출 실패 ({e.response.status_code}): {e.response.text}")
    except Exception as e:
        raise RuntimeError(f"VLM API 호출 실패: {e}")
