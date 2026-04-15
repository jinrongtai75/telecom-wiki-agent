# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

통신사 및 무선통신 단말 개발 엔지니어를 위한 **무선통신프로토콜 위키백과사전 에이전트**.

LGU+ 기술규격서 PDF를 업로드하면 이미지/표/텍스트를 자동 분류하여 ChromaDB에 인덱싱하고, 자연어 질문에 대해 RAG 기반 정확한 답변을 제공하는 웹앱.

## Architecture

```
frontend (React/Vite :5173)
    ↓ HTTP
backend (FastAPI :8000)
    ├─ PDF Pipeline: pdf_parser → noise_remover → image_processor → chunker → vector_store
    ├─ Search: ChromaDB 의미 검색 → answer_gen (JIHYE/Gemini) → 3GPP 폴백
    └─ Auth: JWT (자체 발급) + SQLite (사용자/히스토리)
```

## Commands

### Backend
```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000   # 개발 서버
uv run pytest tests/ -v                             # 전체 테스트
uv run pytest tests/test_auth.py -v                 # 단일 테스트
uv run ruff check app/                              # 린트
uv run ruff format app/                             # 포맷
```

### Frontend
```bash
cd frontend
npm run dev        # 개발 서버 (포트 5173)
npm run build      # 프로덕션 빌드
npm run test       # vitest 실행
npm run lint       # eslint
```

### 전체 실행
```bash
./start.sh
```

## LLM 호출 규칙 (CRITICAL)

**모든 LLM/VLM 호출은 반드시 `app/modules/llm_client.py`의 `LLMClient`를 통해야 한다.**

```python
# ✅ 올바른 방법
from app.modules.llm_client import LLMClient
client = LLMClient(provider="jihye", token="...")
response = await client.complete(messages)

# ❌ 금지: 직접 API 호출
import anthropic  # 금지
import openai     # 금지
import google.generativeai  # 금지 — llm_client를 통할 것
```

### 지원 프로바이더
- **JIHYE 게이트웨이**: `provider="jihye"`, Bearer JWT 토큰 사용
  - Endpoint: `https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6`
  - Headers: `anthropic-version: bedrock-2023-05-31`
- **Gemini**: `provider="gemini"`, Google API 키 사용
  - Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent`

## PDF 처리 파이프라인

1. `pdf_parser.py`: PyMuPDF 2-Pass 파싱 (텍스트/표/이미지 분류)
2. `noise_remover.py`: 헤더/푸터/페이지번호 제거
3. `image_processor.py`: VLM으로 이미지 discard/save/describe 판단
4. `chunker.py`: 섹션 단위 청킹 (512토큰, overlap 64, 표는 분할 금지)
5. `vector_store.py`: ChromaDB + multilingual-e5-large 임베딩

## 검색 규칙

- ChromaDB 쿼리 시 반드시 `"query: "` 접두사 추가 (e5 모델 스펙)
- relevance score < 0.7 → 3GPP FTP 폴백 검색 자동 실행
- 출처(source) 정보는 항상 응답에 포함

## 보안 규칙

- API 키/JWT 토큰은 절대 로그에 출력 금지
- 파일 업로드: PDF만 허용 (MIME 타입 + 확장자 이중 검증)
- 최대 파일 크기: 100MB
- 사용자 입력은 반드시 Pydantic으로 검증 후 사용

## 데이터 저장 위치

```
backend/data/
├── telecom.db       # SQLite (사용자·히스토리·문서 메타)
├── chroma/          # ChromaDB 인덱스
├── documents/       # 업로드된 원본 PDF
└── images/          # 페이지 이미지 캐시 (PNG)
```

## 환경변수 (.env)

```
JIHYE_GATEWAY_URL=https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6
JWT_SECRET=<변경필수>
DATABASE_URL=sqlite:///./data/telecom.db
CHROMA_PATH=./data/chroma
DOCUMENTS_PATH=./data/documents
IMAGES_PATH=./data/images
```
