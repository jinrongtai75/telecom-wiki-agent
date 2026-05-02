# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

통신사 및 무선통신 단말 개발 엔지니어를 위한 **무선통신프로토콜 위키백과사전 에이전트**.

LGU+ 기술규격서 PDF를 업로드하면 이미지/표/텍스트를 자동 분류하여 ChromaDB에 인덱싱하고, 자연어 질문에 대해 RAG 기반 정확한 답변을 제공하는 웹앱.

## 전체 서비스 구조

```
[전처리 프론트엔드]  (React/Vite, Vercel)
      ↓ HTTP
[전처리 백엔드]      (FastAPI, Railway, in-memory)
      ↓ 프록시 (MD + PDF 전달)
[메인 백엔드]        (FastAPI, Railway, PostgreSQL)
      ├─ MD 적재: md_chunker → Gemini 임베딩 → ChromaDB
      ├─ 검색: ChromaDB 의미 검색 → JIHYE/Gemini LLM 답변
      └─ 인증: JWT (자체 발급)
[메인 프론트엔드]    (React/Vite, Vercel)
      ↓ HTTP
[메인 백엔드]
```

## 배포 현황

| 서비스 | URL |
|--------|-----|
| 메인 프론트엔드 | https://telecom-wiki-agent.vercel.app |
| 메인 백엔드 | https://telecom-wiki-agent-production.up.railway.app |
| 전처리 프론트엔드 | https://telecom-wiki-agent-kbbr.vercel.app |
| 전처리 백엔드 | Railway: telecom-wiki-agent-prep-production |
| DB | Railway PostgreSQL (메인 백엔드 연결) |

## 관리자 계정

- **username**: `antonio`
- **password**: `Lguplus2026`
- 관리자만 Gemini API 키 입력 가능 (임베딩 서버 공통 키)

## Commands

### 메인 백엔드
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
uv run pytest tests/ -v
uv run ruff check app/
uv run ruff format app/
```

### 메인 프론트엔드
```bash
cd frontend
npm run dev        # 개발 서버 (포트 5173)
npm run build
npm run test
npm run lint
```

### 전처리 백엔드
```bash
cd preprocessor/backend
uv run uvicorn app.main:app --reload --port 8001
uv run pytest tests/ -v
```

### 전처리 프론트엔드
```bash
cd preprocessor/frontend
npm run dev        # 개발 서버 (포트 5174)
npm run build
```

## LLM 호출 규칙 (CRITICAL)

**모든 LLM/VLM 호출은 반드시 `app/modules/llm_client.py`의 `LLMClient`를 통해야 한다.**
**`api.anthropic.com` 직접 호출 금지** — 사내 DLP 정책.

```python
# ✅ 올바른 방법
from app.modules.llm_client import LLMClient
client = LLMClient(provider="jihye", token="...")
response = await client.complete(messages)

# ❌ 금지
import anthropic
import google.generativeai
```

### 지원 프로바이더
- **JIHYE 게이트웨이**: `provider="jihye"`, Bearer JWT 토큰
  - Endpoint: `https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6`
  - Headers: `anthropic-version: bedrock-2023-05-31`
- **Gemini**: `provider="gemini"`, Google API 키
  - Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`

## 임베딩 (메인 백엔드)

**Gemini text-embedding-004** API (`batchEmbedContents`) — 768차원.

- Gemini API 키 없으면 SHA256 해시 기반 768-dim 폴백 (검색 품질 저하됨)
- 키는 DB `AppSetting` 테이블 `gemini_token` 컬럼에 저장 (관리자 설정 패널에서 입력)
- `vector_store.py`의 `_make_embedding_function()` 참조

> ONNX/sentence-transformers는 Railway 메모리 부족(OOM)으로 제거됨.

## 인증키 역할 분리

| 키 | 용도 | 설정 주체 |
|----|------|-----------|
| JIHYE JWT 토큰 | LLM 답변 생성 (검색 시 사용) | 각 팀원 개별 입력 |
| Gemini API 키 | 임베딩 전용 (적재 시 사용) | 관리자(antonio)만 입력 |

## MD 적재 → 청킹 흐름

```
전처리 도구 (PDF/Word 업로드)
  → MDExporter.export() → <!-- obj:ID type:TYPE order:N confirm:STATUS page:N --> 주석 포함 MD 생성
  → 전처리 백엔드 /api/ingest/to-wiki
    → wiki agent /api/auth/login (antonio / 비밀번호)
    → wiki agent /api/ingest/md
      → md_chunker.chunk_from_text() — obj 주석 파싱 → 섹션별 청크
      → vector_store.index_chunks() — Gemini 임베딩 → ChromaDB
```

### 핵심: `<!-- obj:... -->` 주석 형식

`md_chunker._parse_blocks()`는 이 주석을 블록 경계로 사용한다.
`MDExporter.export()`가 반드시 이 주석을 각 객체 앞에 삽입해야 한다.

```
<!-- obj:abc123 type:text order:1 confirm:confirmed page:3 -->
```

`_OBJ_RE` 정규식 (`md_chunker.py`): `.*?` 와일드카드로 필드 순서 무관하게 파싱.

## 전처리 백엔드 주의사항

- **인메모리 상태**: `_docs` 딕셔너리 → Railway 재배포 시 초기화됨 → 문서 재업로드 필요
- **Wiki Agent 비밀번호**: 설정 패널 UI에서 입력 (Railway 환경변수보다 우선) 또는 `WIKI_AGENT_PASSWORD` 환경변수
- **기본 사용자명**: `antonio` (admin 아님)

## Railway 환경변수 (전처리 백엔드)

| 변수 | 값 |
|------|-----|
| `WIKI_AGENT_USERNAME` | `antonio` |
| `WIKI_AGENT_PASSWORD` | `Lguplus2026` |
| `WIKI_AGENT_URL` | `https://telecom-wiki-agent-production.up.railway.app` |

## 데이터 저장 위치 (메인 백엔드)

```
backend/data/
├── chroma/          # ChromaDB 인덱스
├── documents/       # 업로드된 원본 파일
└── images/          # 이미지 캐시
```

DB: Railway PostgreSQL (`DATABASE_URL` 환경변수)

## 환경변수 (메인 백엔드 .env)

```
DATABASE_URL=postgresql://...    # Railway PostgreSQL
JWT_SECRET=<변경필수>
CHROMA_PATH=./data/chroma
DOCUMENTS_PATH=./data/documents
IMAGES_PATH=./data/images
ADMIN_RESET_SECRET=<선택>        # /api/auth/reset-admin 엔드포인트 보호
```

## 보안 규칙

- API 키/JWT 토큰은 절대 로그에 출력 금지
- 파일 업로드: PDF/Word만 허용 (MIME 타입 + 확장자 이중 검증)
- 최대 파일 크기: 100MB
- 사용자 입력은 반드시 Pydantic으로 검증

## 미완료 항목

- `/api/ingest/check` 엔드포인트 — TDD RED 완료 (테스트 4개 실패), 구현 미완
- E2E 검색 테스트 — JIHYE 토큰 + 질의 → RAG 답변 확인
- 전처리 재배포 시 문서 재업로드 필요한 구조적 한계 (인메모리)
