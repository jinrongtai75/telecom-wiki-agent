# AGENTS.md — 에이전트 역할 정의

## 시스템 에이전트 구성

이 프로젝트는 3개의 논리적 에이전트로 구성된다. 각 에이전트는 독립적으로 동작하며 명확한 입력/출력 인터페이스를 갖는다.

---

## Agent 1: Preprocessing Agent (전처리 에이전트)

**역할**: PDF 문서를 수신하여 고품질 청크로 변환하고 벡터 DB에 인덱싱

**트리거**: `POST /api/documents/upload`

**파이프라인**:
```
PDF bytes
  → pdf_parser.py        # 2-Pass 파싱: 텍스트/표/이미지 분류
  → noise_remover.py     # 헤더/푸터/페이지번호 제거
  → image_processor.py   # VLM: discard/save/describe
  → chunker.py           # 섹션 단위 청킹 (512토큰, overlap 64)
  → vector_store.py      # ChromaDB 인덱싱
  → SQLite               # 문서 메타데이터 저장
```

**출력**: `{"doc_id": "...", "chunks": N, "status": "indexed"}`

**제약**:
- PDF 전용 (MIME 검증 필수)
- 최대 100MB
- VLM 호출은 반드시 `llm_client.py` 경유

---

## Agent 2: Search Agent (검색 에이전트)

**역할**: 자연어 질문을 수신하여 관련 청크를 검색하고 컨텍스트 구성

**트리거**: `POST /api/search` 내부 호출

**파이프라인**:
```
사용자 질문 (str)
  → llm_client.py        # 영어 키워드 추출 (한국어 질문 최적화)
  → vector_store.py      # ChromaDB top-10 의미 검색
  → relevance 판단       # score < 0.7 → 3GPP 폴백
  → threegpp.py          # (폴백) 3GPP FTP 검색
  → 컨텍스트 구성        # chunks + sources 리스트
```

**출력**: `{"chunks": [...], "sources": [...], "from_3gpp": bool}`

**제약**:
- ChromaDB 쿼리는 반드시 `"query: "` 접두사 포함
- 3GPP 폴백은 relevance score 기준으로만 자동 실행 (임의 비활성화 금지)

---

## Agent 3: Answer Generation Agent (답변 생성 에이전트)

**역할**: 검색된 컨텍스트 + 사용자 질문으로 최종 답변 생성

**트리거**: `POST /api/search` 내부 호출 (Search Agent 완료 후)

**파이프라인**:
```
{question, chunks, sources, provider, token}
  → answer_gen.py        # 프롬프트 구성 + LLM 호출
  → llm_client.py        # JIHYE or Gemini API
  → SQLite               # 히스토리 저장 (user_id, question, answer, sources)
```

**출력**: `{"answer": "...", "sources": [...], "model": "..."}`

**프롬프트 규칙**:
- 시스템 프롬프트: "당신은 LGU+ 무선통신 프로토콜 전문가입니다..."
- 컨텍스트 없을 때: 자체 지식 기반 답변 허용 (3GPP 표준 지식)
- 마크다운 사용 허용 (프론트엔드에서 렌더링)
- 출처 인용 필수: 답변에 [출처: 문서명 p.N] 형식 포함

---

## 에이전트 간 데이터 흐름

```
[사용자]
    │ POST /api/search {question, provider, token}
    ▼
[FastAPI Router: search.py]
    │
    ├──[Auth 검증] → 실패 시 401 반환
    │
    ├──[Search Agent]
    │    └─ ChromaDB 검색 → chunks, sources
    │
    └──[Answer Generation Agent]
         ├─ JIHYE 게이트웨이 (provider=jihye)
         └─ Gemini API (provider=gemini)
              │
              ▼
         {answer, sources} → SQLite 저장 → 응답 반환
```

---

## 오류 처리 정책

| 상황 | 처리 |
|------|------|
| PDF 파싱 실패 | 청크 0개로 부분 인덱싱, 에러 로그 기록 |
| ChromaDB 검색 결과 없음 | 3GPP 폴백 자동 실행 |
| 3GPP 폴백도 실패 | 자체 지식 기반 답변 (명시적 고지) |
| LLM API 오류 | 503 반환 + 에러 메시지 포함 |
| 인증 실패 | 401 반환, 토큰 정보 로그 금지 |
