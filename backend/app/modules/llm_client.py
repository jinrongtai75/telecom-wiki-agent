"""
LLM/VLM 통합 클라이언트.

지원 프로바이더:
  - jihye: LGU+ JIHYE 게이트웨이 (Claude Sonnet, Bedrock 스타일)
  - gemini: Google Gemini API

모든 LLM 호출은 이 모듈을 통해야 한다. 직접 anthropic/openai 임포트 금지.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator

import httpx

from app.config import settings


class LLMClient:
    def __init__(self, provider: str, api_token: str):
        """
        provider: "jihye" | "gemini"
        api_token: JIHYE JWT 토큰 or Gemini API 키
        """
        if provider not in ("jihye", "gemini"):
            raise ValueError(f"Unknown provider: {provider}")
        self.provider = provider
        self.api_token = api_token

    # ── 텍스트 완성 ─────────────────────────────────────────────────────────

    def complete(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2000,
    ) -> str:
        if self.provider == "jihye":
            return self._jihye_complete(prompt, system, max_tokens)
        return self._gemini_complete(prompt, system, max_tokens)

    # ── 스트리밍 텍스트 완성 ──────────────────────────────────────────────────

    def complete_stream(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        """텍스트 토큰을 스트리밍으로 yield."""
        if self.provider == "jihye":
            yield from self._jihye_complete_stream(prompt, system, max_tokens)
        else:
            yield from self._gemini_complete_stream(prompt, system, max_tokens)

    # ── VLM (이미지 + 텍스트) ───────────────────────────────────────────────

    def complete_with_image(
        self,
        prompt: str,
        image_b64: str,
        media_type: str = "image/png",
        max_tokens: int = 1000,
    ) -> str:
        """
        image_b64: 순수 base64 (data URI 접두어 없이)
        또는 data URI 형식 (자동으로 접두어 제거)
        """
        # data URI 접두어 제거
        if image_b64.startswith("data:"):
            match = re.match(r"data:([^;]+);base64,(.+)", image_b64, re.DOTALL)
            if match:
                media_type = match.group(1)
                image_b64 = match.group(2)

        if self.provider == "jihye":
            return self._jihye_vlm(prompt, image_b64, media_type, max_tokens)
        return self._gemini_vlm(prompt, image_b64, media_type, max_tokens)

    # ── JIHYE 게이트웨이 구현 ────────────────────────────────────────────────

    def _jihye_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "anthropic-version": "bedrock-2023-05-31",
            "Content-Type": "application/json",
        }

    def _jihye_complete(self, prompt: str, system: str, max_tokens: int) -> str:
        messages = [{"role": "user", "content": prompt}]
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system

        resp = httpx.post(
            settings.jihye_gateway_url,
            headers=self._jihye_headers(),
            json=body,
            timeout=60,
            verify=False,
        )
        resp.raise_for_status()
        outer = resp.json()
        inner = json.loads(outer["content"])
        return inner["content"][0]["text"].strip()

    def _jihye_vlm(self, prompt: str, image_b64: str, media_type: str, max_tokens: int) -> str:
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
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        resp = httpx.post(
            settings.jihye_gateway_url,
            headers=self._jihye_headers(),
            json=body,
            timeout=60,
            verify=False,
        )
        resp.raise_for_status()
        outer = resp.json()
        inner = json.loads(outer["content"])
        return inner["content"][0]["text"].strip()

    # ── Gemini API 구현 ──────────────────────────────────────────────────────

    _GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def _gemini_complete(self, prompt: str, system: str, max_tokens: int) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        resp = httpx.post(
            f"{self._GEMINI_URL}?key={self.api_token}",
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _gemini_vlm(self, prompt: str, image_b64: str, media_type: str, max_tokens: int) -> str:
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": media_type,
                                "data": image_b64,
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        resp = httpx.post(
            f"{self._GEMINI_URL}?key={self.api_token}",
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    # ── 스트리밍 구현 ────────────────────────────────────────────────────────

    def _jihye_complete_stream(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        """JIHYE 게이트웨이 SSE 스트리밍. event: content_block_delta 파싱."""
        messages = [{"role": "user", "content": prompt}]
        body: dict = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
        }
        if system:
            body["system"] = system

        url = settings.jihye_gateway_url
        # JIHYE 스트리밍 엔드포인트: /stream 접미사 추가 (없으면 그대로 시도)
        if not url.endswith("/stream"):
            stream_url = url + "/stream"
        else:
            stream_url = url

        try:
            with httpx.stream(
                "POST",
                stream_url,
                headers=self._jihye_headers(),
                json=body,
                timeout=120,
                verify=False,
            ) as resp:
                if resp.status_code == 404:
                    # 스트리밍 엔드포인트 미지원 → 비스트리밍 폴백
                    yield self._jihye_complete(prompt, system, max_tokens)
                    return
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str in ("", "[DONE]"):
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    # Bedrock SSE: {"type":"content_block_delta","delta":{"text":"..."}}
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        text = delta.get("text") or delta.get("delta", {}).get("text", "")
                        if text:
                            yield text
        except Exception:
            # 스트리밍 실패 시 비스트리밍 폴백
            yield self._jihye_complete(prompt, system, max_tokens)

    _GEMINI_STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent"

    def _gemini_complete_stream(self, prompt: str, system: str, max_tokens: int) -> Iterator[str]:
        """Gemini SSE 스트리밍."""
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
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    try:
                        text = event["candidates"][0]["content"]["parts"][0]["text"]
                        if text:
                            yield text
                    except (KeyError, IndexError):
                        continue
        except Exception:
            # 스트리밍 실패 시 비스트리밍 폴백
            yield self._gemini_complete(prompt, system, max_tokens)
