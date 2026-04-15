# CLAUDE.md — 프로젝트 개발 가이드

## LLM / VLM API 호출 규칙

### 필수 원칙

**`api.anthropic.com` 직접 호출 금지** — 사내 DLP 정책으로 차단됨.
모든 Claude LLM/VLM 호출은 반드시 **JIHYE 게이트웨이**를 경유해야 한다.

---

### JIHYE 게이트웨이 스펙

| 항목 | 값 |
|------|-----|
| 엔드포인트 | `https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6` |
| 인증 헤더 | `Authorization: Bearer <JWT_TOKEN>` |
| 필수 헤더 | `anthropic-version: bedrock-2023-05-31` |
| Content-Type | `application/json` |

JWT 토큰은 `.env` 파일의 `JIHYE_TOKEN` 환경변수에서 읽는다.

---

### 요청 포맷 (Bedrock 스타일)

OpenAI `/v1/chat/completions` 포맷이 아닌 **Anthropic Messages API** 포맷을 사용한다.

```python
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "messages": [
        {
            "role": "user",
            "content": "프롬프트 텍스트"   # 텍스트 전용
        }
    ]
}
```

이미지(VLM) 포함 시:

```python
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",   # 실제 타입에 맞게
                        "data": "<base64_string>"    # data:image/png;base64, 접두어 제거
                    }
                },
                {
                    "type": "text",
                    "text": "프롬프트 텍스트"
                }
            ]
        }
    ]
}
```

---

### 응답 파싱

게이트웨이는 응답을 **이중 JSON**으로 감싸서 반환한다.

```python
outer = resp.json()                          # outer: {"content": "<JSON 문자열>", ...}
import json
inner = json.loads(outer["content"])         # inner: Anthropic Messages 응답 객체
text = inner["content"][0]["text"]           # 최종 텍스트 추출
```

---

### 구현 위치 및 적용 범위

아래 세 모듈의 모든 LLM/VLM 호출을 JIHYE 게이트웨이 방식으로 교체한다.

| 파일 | 대상 메서드 |
|------|------------|
| `backend/app/modules/table_processor.py` | `_call_llm()`, `review_with_vlm()`, `flatten_with_vlm()` |
| `backend/app/modules/image_processor.py` | `_call_llm()`, `_call_vlm()`, `review_with_vlm()` |
| `backend/app/modules/summary_generator.py` | `_call_llm()` |

공통 게이트웨이 클라이언트는 `backend/app/modules/llm_client.py`에 단일 구현하고
각 모듈에서 임포트하여 사용한다.

---

### 구현 예시 (`llm_client.py`)

```python
import os, json, httpx

JIHYE_ENDPOINT = "https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6"

def _headers() -> dict:
    token = os.environ.get("JIHYE_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "bedrock-2023-05-31",
        "Content-Type": "application/json",
    }

def call_llm(prompt: str, max_tokens: int = 1000) -> str:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(JIHYE_ENDPOINT, headers=_headers(), json=body, timeout=60)
    resp.raise_for_status()
    outer = resp.json()
    inner = json.loads(outer["content"])
    return inner["content"][0]["text"].strip()

def call_vlm(image_b64: str, media_type: str, prompt: str, max_tokens: int = 1000) -> str:
    """image_b64: data URI 접두어 없는 순수 base64 문자열"""
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
    resp = httpx.post(JIHYE_ENDPOINT, headers=_headers(), json=body, timeout=60)
    resp.raise_for_status()
    outer = resp.json()
    inner = json.loads(outer["content"])
    return inner["content"][0]["text"].strip()
```

---

### `.env` 설정

```dotenv
JIHYE_TOKEN=<JWT 토큰>
```

`backend/app/modules/api_key_manager.py`의 `JIHYE` 키 또는 `.env` 직접 로드 방식 중 하나로 관리.
기존 `LLM` / `VLM` 키(OpenAI)는 게이트웨이 전환 후 불필요해지면 제거한다.

---

### 금지 사항

- `https://api.openai.com` 직접 호출 금지
- `https://api.anthropic.com` 직접 호출 금지
- `anthropic` Python SDK 직접 임포트 금지 (게이트웨이 우회 위험)
- 토큰을 소스코드에 하드코딩 금지 — 반드시 환경변수로 관리
