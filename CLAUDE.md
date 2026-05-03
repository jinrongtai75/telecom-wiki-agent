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
      ├─ 검색: ChromaDB 의미 검색 → Gemini LLM 답변
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
| 전처리 백엔드 | https://telecom-wiki-agent-prep-production.up.railway.app |
| DB | Railway PostgreSQL (메인 백엔드 연결) |

## 관리자 계정

- **username**: `antonio`
- **password**: `Lguplus2026`

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

**모든 LLM/VLM 호출은 반드시 `app/modules/llm_client.py`를 통해야 한다.**

### 메인 백엔드 (`backend/app/modules/llm_client.py`)

```python
from app.modules.llm_client import LLMClient
client = LLMClient(api_token="...")   # provider 파라미터 없음 — Gemini 전용
response = client.complete(prompt)
```

### 전처리 백엔드 (`preprocessor/backend/app/modules/llm_client.py`)

```python
from app.modules.llm_client import call_llm, call_vlm
text = call_llm(prompt)
text = call_vlm(image_b64, prompt)   # image_b64: data URI 또는 순수 base64
```

- API 키 조회 순서: `GEMINI_API_KEY` 환경변수 → `.env` 파일 → 없으면 RuntimeError
- **모델**: `gemini-2.5-flash` (2026년 3월 이후 신규 프로젝트에서 `gemini-2.0-flash`는 404)

### 지원 프로바이더

**Gemini만 지원** (JIHYE 게이트웨이는 완전 제거됨 — 사내 인트라넷 전용으로 외부 접근 불가)

- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
- 인증: `?key={GEMINI_API_KEY}` 쿼리 파라미터

## Gemini API 키 관리

**Railway Variables에서만 관리** — UI 입력 불필요, 재시작해도 유지됨.

| 서비스 | 변수명 | 비고 |
|--------|--------|------|
| 메인 백엔드 | `GEMINI_API_KEY` | Railway Variables |
| 전처리 백엔드 | `GEMINI_API_KEY` | Railway Variables |

### 메인 백엔드 키 조회 우선순위 (`_get_llm()`, `_make_embedding_function()`)

1. 요청 body의 `api_token` (레거시 — 현재 프론트엔드에서 빈 문자열 전송)
2. `os.environ.get("GEMINI_API_KEY")` ← **주 경로**
3. DB `AppSetting.gemini_token` (이전에 UI로 저장한 값, fallback)

### 전처리 백엔드 키 조회 우선순위

1. `os.environ.get("GEMINI_API_KEY")` ← **주 경로**
2. `APIKeyManager().get_key("GEMINI")` → `.env` 파일 조회

> 로컬 개발 시에는 `preprocessor/backend/.env`에 `GEMINI_API_KEY=AIza...` 직접 추가.

## 임베딩 (메인 백엔드)

**Gemini `gemini-embedding-001`** API (`batchEmbedContents`) — 3072차원.

- 키 조회: `GEMINI_API_KEY` env var → DB fallback → 없으면 SHA256 해시 폴백 (검색 품질 저하)
- `vector_store.py`의 `_make_embedding_function()` 참조

> ONNX/sentence-transformers는 Railway 메모리 부족(OOM)으로 제거됨.

## 전처리 에이전트 주요 기능

| 기능 | 엔드포인트 | 설명 |
|------|-----------|------|
| 문서 업로드 | `POST /api/documents/upload` | PDF/Word 파싱 |
| 노이즈 제거 | `POST /api/documents/{id}/denoise` | 반복 텍스트 제거 |
| 소제목 요약 | `POST /api/documents/{id}/summarize-selection` | Gemini LLM 요약 |
| Table 검수 | `POST /api/objects/{id}/{obj}/table/review` | Gemini VLM으로 표 품질 검수 |
| Image 검수 | `POST /api/objects/{id}/{obj}/image/review` | Gemini VLM으로 이미지 처리 방식 결정 |
| VLM 이미지 해석 | `POST /api/objects/{id}/{obj}/image/interpret` | Gemini VLM으로 이미지 상세 설명 |
| MD 내보내기 | `GET /api/documents/{id}/export` | 마크다운 다운로드 |
| Wiki 적재 | `POST /api/ingest/to-wiki` | 메인 백엔드에 RAG 적재 |
| RAG 현황 조회 | `GET /api/ingest/rag-documents` | 적재된 문서 목록 (메인 백엔드 프록시) |

## 전처리 백엔드 주의사항

### 인메모리 상태 소실 (구조적 한계)

`_docs` 딕셔너리는 Railway 프로세스 재시작 시 초기화됨.
코드 배포(`git push`) → Railway 자동 재배포 → 기존 업로드 문서 모두 소실.

**증상**: 모든 `/api/objects/` 엔드포인트에서 404 "문서를 찾을 수 없습니다" 반환.
**대처**: PDF를 다시 업로드하면 즉시 해결됨.

프론트엔드 처리:
- `silentApi`(인터셉터 없음)를 사용하는 배치성 API (`reviewImage`, `reviewTable`, `denoise` 등)는 호출 측에서 404 감지 후 loop break
- `api`(글로벌 인터셉터 있음)를 사용하는 나머지 API는 interceptor에서 404 + "문서/객체" 키워드 감지 → "PDF를 다시 업로드해주세요" 안내

### Table 검수 / Image 검수 JSON 파싱

`table_processor.py`의 `review_with_vlm()`, `review_with_llm()`:
- `max_tokens=4000`, `json_mode=True` (Gemini `responseMimeType: "application/json"`)
- `_parse_json()` static method: 마크다운 코드블록 제거 → `json.loads` → regex fallback

`image_processor.py`의 `review_with_vlm()`:
- `json_mode` 없음 (Gemini가 JSON을 잘 반환함)
- 마크다운 코드블록(`\`\`\``) 제거 후 파싱

### Wiki Agent 비밀번호

설정 패널 UI에서 입력 → `preprocessor/backend/.env`에 저장 (Railway 재시작 시 소실 가능).
안정적 운영을 위해 Railway Variables `WIKI_AGENT_PASSWORD` 환경변수 설정 권장.

### 한글 파일명

`Content-Disposition` 헤더는 RFC 5987(`filename*=UTF-8''...`) 형식으로 처리 — latin-1 직접 삽입 시 500 에러.

## Railway 환경변수

### 메인 백엔드 (`telecom-wiki-agent`)

| 변수 | 값 |
|------|-----|
| `DATABASE_URL` | Railway PostgreSQL 연결 문자열 |
| `JWT_SECRET` | JWT 서명 비밀키 |
| `CHROMA_PATH` | `./data/chroma` |
| `DOCUMENTS_PATH` | `./data/documents` |
| `IMAGES_PATH` | `./data/images` |
| `GEMINI_API_KEY` | Gemini API 키 |

### 전처리 백엔드 (`telecom-wiki-agent-prep`)

| 변수 | 값 |
|------|-----|
| `GEMINI_API_KEY` | Gemini API 키 |
| `WIKI_AGENT_USERNAME` | `antonio` |
| `WIKI_AGENT_PASSWORD` | `Lguplus2026` |
| `WIKI_AGENT_URL` | `https://telecom-wiki-agent-production.up.railway.app` |

## 전처리 에이전트 설정 패널

**Wiki Agent 비밀번호만** UI에서 관리. Gemini API 키는 Railway Variables 전용.

- 설정 패널 위치: 사이드바 하단 "API 키 / 연동 설정" 버튼
- 컴포넌트: `preprocessor/frontend/src/components/SettingsPanel.tsx`

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

### MDExporter 이미지 처리 규칙

- **검수 완료 이미지** (`image_path` 있음): 설명 텍스트 + `<!-- image: path -->` 주석
- **검수 미완료 이미지** (base64 content): `[이미지: ID]` 플레이스홀더로 대체
  - base64를 MD에 그대로 삽입하면 응답이 수 MB로 불어나 network error 발생
- **URL 이미지**: `![alt](url)` 마크다운 그대로 유지

## Vercel 배포 전략

**메인·전처리 프론트엔드 모두 `git push origin main` 한 번으로 자동 배포된다.**

| 프로젝트 | rootDirectory | 프로덕션 브랜치 |
|---------|--------------|--------------|
| `telecom-wiki-agent` (메인) | `frontend` | `main` |
| `telecom-wiki-agent-kbbr` (전처리) | `preprocessor/frontend` | `main` |

- 두 프로젝트 모두 GitHub `main` 브랜치 push → Vercel 자동 빌드·배포
- `npx vercel --prod` CLI 수동 배포는 불필요 (긴급 핫픽스 시에만 사용)
- 사내 SSL 프록시 환경에서 CLI 사용 시 `NODE_TLS_REJECT_UNAUTHORIZED=0` 필요

## 데이터 저장 위치 (메인 백엔드)

```
backend/data/
├── chroma/          # ChromaDB 인덱스
├── documents/       # 업로드된 원본 파일
└── images/          # 이미지 캐시
```

DB: Railway PostgreSQL (`DATABASE_URL` 환경변수)

## 보안 규칙

- API 키/JWT 토큰은 절대 로그에 출력 금지
- 파일 업로드: PDF/Word만 허용 (MIME 타입 + 확장자 이중 검증)
- 최대 파일 크기: 100MB
- 사용자 입력은 반드시 Pydantic으로 검증

## RAG 데이터 조회

전처리 에이전트 사이드바 **RAG 현황** 섹션에서 적재된 문서 목록 확인 가능.
직접 API 호출:

```bash
# 로그인 → 토큰 취득
TOKEN=$(curl -s -X POST https://telecom-wiki-agent-production.up.railway.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"antonio","password":"Lguplus2026"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# 적재 문서 목록
curl -s https://telecom-wiki-agent-production.up.railway.app/api/documents \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import json,sys
for d in json.load(sys.stdin):
    print(d['status'], d.get('chunk_count',0), d['original_name'])
"
```

## 미완료 항목

- `/api/ingest/check` 엔드포인트 — TDD RED 완료 (테스트 4개 실패), 구현 미완
- 전처리 재배포 시 문서 재업로드 필요한 구조적 한계 (인메모리 → DB/스토리지 전환 검토 가능)
