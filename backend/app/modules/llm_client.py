"""
LLM/VLM 클라이언트 — Google Gemini API 전용.
모든 LLM 호출은 이 모듈을 통해야 한다.
"""
from __future__ import annotations

import time
from collections.abc import Iterator

import httpx


def _post_with_retry(url: str, json: dict, timeout: int) -> httpx.Response:
    """429 발생 시 지수 백오프로 최대 5회 재시도."""
    for attempt in range(5):
        resp = httpx.post(url, json=json, timeout=timeout)
        if resp.status_code != 429:
            resp.raise_for_status()
            return resp
        wait = 2 ** attempt * 5  # 5, 10, 20, 40, 80초
        time.sleep(wait)
    resp.raise_for_status()
    return resp


class LLMClient:
    _GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    _GEMINI_STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent"

    def __init__(self, provider: str = "gemini", api_token: str = ""):
        self.api_token = api_token

    def complete(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        resp = _post_with_retry(
            f"{self._GEMINI_URL}?key={self.api_token}",
            json=body,
            timeout=60,
        )
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def complete_stream(self, prompt: str, system: str = "", max_tokens: int = 2000) -> Iterator[str]:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        try:
            with httpx.stream(
                "POST",
                f"{self._GEMINI_STREAM_URL}?key={self.api_token}&alt=sse",
                json=body,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str in ("", "[DONE]"):
                        continue
                    try:
                        import json
                        event = json.loads(data_str)
                        text = event["candidates"][0]["content"]["parts"][0]["text"]
                        if text:
                            yield text
                    except (KeyError, IndexError, Exception):
                        continue
        except Exception:
            yield self.complete(prompt, system, max_tokens)

    def complete_with_image(
        self,
        prompt: str,
        image_b64: str,
        media_type: str = "image/png",
        max_tokens: int = 1000,
    ) -> str:
        import re
        if image_b64.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.+)", image_b64, re.DOTALL)
            if match:
                media_type = match.group(1)
                image_b64 = match.group(2)

        body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": media_type, "data": image_b64}},
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        resp = _post_with_retry(
            f"{self._GEMINI_URL}?key={self.api_token}",
            json=body,
            timeout=60,
        )
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
