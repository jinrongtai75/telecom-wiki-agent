# Implementation Plan: 문서 전처리 도구 (Doc Preprocessing Tool)

## Overview

Backend(FastAPI + Python)와 Frontend(React + Ant Design)로 구성된 RAG 문서 전처리 웹 애플리케이션을 구현한다. 백엔드 모듈(Parser, NoiseRemover, SummaryGenerator, TableProcessor, ImageProcessor, JSONExporter, APIKeyManager)을 먼저 구축하고, REST API 엔드포인트를 연결한 뒤, 프론트엔드 컴포넌트를 구현하여 통합한다.

## Tasks

- [x] 1. 프로젝트 구조 및 데이터 모델 설정
  - [x] 1.1 백엔드 프로젝트 초기화 및 의존성 설정
    - `uv init` 으로 Python 프로젝트 생성
    - `pyproject.toml`에 fastapi, uvicorn, pymupdf, python-docx, beautifulsoup4, requests, pandas, python-dotenv, pydantic, httpx, cryptography 의존성 추가
    - pytest, hypothesis 테스트 의존성 추가
    - 디렉토리 구조 생성: `backend/app/`, `backend/app/modules/`, `backend/app/api/`, `backend/tests/`
    - _Requirements: 전체_

  - [x] 1.2 핵심 데이터 모델 정의
    - `backend/app/models.py`에 Pydantic 모델 구현: `ObjectType`, `ConfirmStatus`, `DocumentFormat`, `DocumentObject`, `NoisePatterns`, `ParseResult`, `ProcessedDocument`
    - 설계 문서의 Data Models 섹션 그대로 구현
    - _Requirements: 1.1, 1.2, 1.3, 9.1, 9.2_

  - [ ]* 1.3 데이터 모델 Property 테스트 작성
    - **Property 1: Parser output type validity** — DocumentObject의 type이 항상 text/image/table 중 하나이고 order가 유효한지 검증
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [x] 1.4 프론트엔드 프로젝트 초기화
    - React + TypeScript 프로젝트 생성 (Vite)
    - antd, axios 의존성 설치
    - Jest + React Testing Library 테스트 환경 설정
    - 디렉토리 구조 생성: `frontend/src/components/`, `frontend/src/api/`, `frontend/src/types/`
    - _Requirements: 2.3_

  - [x] 1.5 프론트엔드 타입 정의
    - `frontend/src/types/index.ts`에 백엔드 모델과 대응하는 TypeScript 인터페이스 정의
    - `DocumentObject`, `ParseResult`, `ProcessedDocument`, `NoisePatterns` 등
    - _Requirements: 1.4, 9.1_

- [x] 2. API Key Manager 구현
  - [x] 2.1 APIKeyManager 모듈 구현
    - `backend/app/modules/api_key_manager.py` 생성
    - `save_key()`: dotenv 파일에 API 키 저장
    - `get_key()`: 저장된 API 키 반환
    - `validate_key()`: 외부 API 호출로 키 유효성 검증
    - _Requirements: 8.2, 8.3, 8.4_

  - [ ]* 2.2 APIKeyManager Property 테스트 작성
    - **Property 15: API key storage round-trip** — save_key 후 get_key가 동일한 키를 반환하는지 검증
    - **Validates: Requirements 8.2, 8.3**

  - [x] 2.3 API Key REST 엔드포인트 구현
    - `GET /api/settings/keys`: API 키 목록 조회
    - `POST /api/settings/keys`: API 키 저장
    - `POST /api/settings/keys/validate`: API 키 유효성 검증
    - _Requirements: 8.1, 8.2, 8.4_

- [x] 3. Parser 모듈 구현
  - [x] 3.1 PDF Parser 구현
    - `backend/app/modules/parser.py` 생성
    - PyMuPDF를 사용하여 PDF에서 text, image, table 객체 추출
    - 각 객체에 order, page, metadata(폰트 크기, 볼드 등) 설정
    - 소제목 자동 식별 (`is_heading` 설정): 폰트 크기, 볼드 기반 휴리스틱
    - _Requirements: 1.1, 4.1_

  - [x] 3.2 Word Parser 구현
    - python-docx를 사용하여 Word 문서에서 text, image, table 객체 추출
    - heading 스타일 기반 소제목 식별
    - _Requirements: 1.2, 4.1_

  - [x] 3.3 Web Page Parser 구현
    - BeautifulSoup4 + requests를 사용하여 웹 페이지에서 text, image, table 객체 추출
    - HTML heading 태그(h1~h6) 기반 소제목 식별
    - _Requirements: 1.3, 4.1_

  - [x] 3.4 파일 형식 감지 및 라우팅
    - `_detect_format()`: 파일 확장자 및 MIME 타입 기반 형식 감지
    - 지원하지 않는 형식에 대한 오류 처리
    - _Requirements: 1.5, 1.6_

  - [ ]* 3.5 Parser Property 테스트 작성
    - **Property 5: Heading identification** — heading 속성이 있는 요소는 is_heading=True, 없는 요소는 False인지 검증
    - **Validates: Requirements 4.1**

  - [x] 3.6 문서 업로드 REST 엔드포인트 구현
    - `POST /api/documents/upload`: 파일 업로드 및 파싱
    - `POST /api/documents/parse-url`: URL 기반 웹 페이지 파싱
    - 인메모리 문서 저장소 (dict) 구현
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

- [x] 4. Checkpoint - 핵심 파싱 모듈 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Noise Remover 구현
  - [x] 5.1 NoiseRemover 모듈 구현
    - `backend/app/modules/noise_remover.py` 생성
    - 기본 패턴: 페이지 번호(`^\d+$`, `^- \d+ -$`), 반복 헤더/푸터 감지
    - 커스텀 패턴: 사용자 정의 정규식 패턴 적용
    - 잘못된 정규식 패턴 오류 처리
    - _Requirements: 3.1, 3.4, 3.5, 3.6_

  - [ ]* 5.2 NoiseRemover Property 테스트 작성 (기본 패턴)
    - **Property 3: Default noise removal** — 기본 노이즈 패턴이 제거되고 비노이즈 콘텐츠가 보존되는지 검증
    - **Validates: Requirements 3.1**

  - [ ]* 5.3 NoiseRemover Property 테스트 작성 (커스텀 패턴)
    - **Property 4: Custom pattern noise removal** — 커스텀 정규식 패턴이 올바르게 적용되는지 검증
    - **Validates: Requirements 3.4, 3.5, 3.6**

  - [x] 5.4 노이즈 제거 REST 엔드포인트 구현
    - `POST /api/documents/{id}/denoise`: 노이즈 제거 실행
    - 커스텀 패턴 요청 바디 지원
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 6. Summary Generator 구현
  - [x] 6.1 SummaryGenerator 모듈 구현
    - `backend/app/modules/summary_generator.py` 생성
    - `identify_headings()`: 소제목 객체 인덱스 목록 반환
    - `generate_summaries()`: LLM API 호출하여 요약문 생성 후 소제목 아래 삽입
    - API 키 미등록 시 안내 메시지 반환
    - _Requirements: 4.1, 4.2, 4.4, 4.5_

  - [ ]* 6.2 SummaryGenerator Property 테스트 작성
    - **Property 6: Summary insertion structure** — 요약 생성 후 각 heading 뒤에 summary 타입 객체가 삽입되고 총 객체 수가 올바른지 검증
    - **Validates: Requirements 4.2, 4.4**

  - [x] 6.3 수동 소제목 지정 기능 구현
    - 텍스트 객체의 `is_heading` 플래그를 수동으로 변경하는 로직
    - _Requirements: 4.3_

  - [ ]* 6.4 수동 소제목 지정 Property 테스트 작성
    - **Property 7: Manual heading designation** — is_heading 변경 시 다른 필드(content, order, type)가 변경되지 않는지 검증
    - **Validates: Requirements 4.3**

  - [x] 6.5 소제목 요약 REST 엔드포인트 구현
    - `POST /api/documents/{id}/summarize`: 소제목 요약문 생성
    - _Requirements: 4.2, 4.4, 4.5_

- [x] 7. Table Processor 구현
  - [x] 7.1 TableProcessor 모듈 구현
    - `backend/app/modules/table_processor.py` 생성
    - `to_dataframe()`: pandas를 사용하여 테이블 문자열 변환
    - `flatten_with_llm()`: LLM을 통한 텍스트 변환
    - `chat_edit()`: 채팅 기반 LLM 수정
    - API 키 미등록 시 안내 메시지 반환
    - _Requirements: 6.1, 6.2, 6.5, 6.7_

  - [ ]* 7.2 TableProcessor Property 테스트 작성
    - **Property 9: Table pandas conversion produces output** — 유효한 테이블 데이터에 대해 to_dataframe()이 비어있지 않은 문자열을 반환하는지 검증
    - **Validates: Requirements 6.1**

  - [x] 7.3 테이블 처리 REST 엔드포인트 구현
    - `POST /api/objects/{id}/table/process`: pandas 변환
    - `POST /api/objects/{id}/table/flatten`: LLM flattening
    - `POST /api/objects/{id}/table/chat`: 채팅 수정
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 8. Image Processor 구현
  - [x] 8.1 ImageProcessor 모듈 구현
    - `backend/app/modules/image_processor.py` 생성
    - `save_and_link()`: 이미지 저장 + 텍스트에 `<경로>` 삽입
    - `interpret_with_vlm()`: VLM을 통한 이미지 해석
    - `chat_edit()`: 채팅 기반 VLM/LLM 수정
    - API 키 미등록 시 안내 메시지 반환
    - _Requirements: 7.1, 7.2, 7.3, 7.6, 7.8_

  - [ ]* 8.2 ImageProcessor Property 테스트 작성
    - **Property 11: Image link and save** — save_and_link 후 image_path가 비어있지 않고 대상 텍스트에 경로가 포함되는지 검증
    - **Validates: Requirements 7.2**

  - [x] 8.3 이미지 처리 REST 엔드포인트 구현
    - `POST /api/objects/{id}/image/link`: 이미지 링크 연결
    - `POST /api/objects/{id}/image/interpret`: VLM 해석
    - `POST /api/objects/{id}/image/chat`: 채팅 수정
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_

- [x] 9. 객체 Confirm 및 수동 객체 지정 구현
  - [x] 9.1 객체 Confirm 엔드포인트 구현
    - `POST /api/objects/{id}/confirm`: confirm_status를 CONFIRMED로 변경, processed_content 저장
    - 멱등성 보장: 이미 확인된 객체 재확인 시 상태 유지
    - _Requirements: 6.6, 7.7_

  - [ ]* 9.2 객체 Confirm Property 테스트 작성
    - **Property 10: Object confirmation state transition** — confirm 후 상태가 CONFIRMED이고 멱등성이 보장되는지 검증
    - **Validates: Requirements 6.6, 7.7**

  - [x] 9.3 수동 객체 지정 엔드포인트 구현
    - `POST /api/documents/{id}/objects/manual`: 수동 table/image 객체 추가
    - 객체 목록에 새 DocumentObject 추가, order 재정렬
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 9.4 수동 객체 지정 Property 테스트 작성
    - **Property 8: Manual object designation** — 수동 지정 후 객체 수가 1 증가하고 지정된 타입이 올바른지 검증
    - **Validates: Requirements 5.2, 5.3**

- [x] 10. Checkpoint - 백엔드 모듈 전체 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. MD Exporter 구현
  - [x] 11.1 MDExporter 모듈 구현
    - `backend/app/modules/md_exporter.py` 생성
    - `export()`: ProcessedDocument를 Markdown 문자열로 직렬화
      - text → 본문, heading → `##`/`###`, summary → `>` 인용문 블록
      - table → GFM 테이블, image(링크) → `![id](path)`, image(VLM) → 해석 텍스트
      - 각 객체 앞에 메타데이터 HTML 주석(`<!-- obj:... -->`) 삽입
    - `load()`: Markdown 문자열에서 ProcessedDocument 복원
    - `validate_all_confirmed()`: 미확인 table/image 객체 ID 목록 반환
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3_

  - [ ]* 11.2 Markdown 내보내기 완전성 Property 테스트 작성
    - **Property 12: Markdown export completeness** — 내보낸 Markdown의 객체 수와 메타데이터 주석 필드가 원본과 일치하는지 검증
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4**

  - [ ]* 11.3 미확인 객체 경고 Property 테스트 작성
    - **Property 13: Unconfirmed object export warning** — PENDING 상태 table/image 객체가 있을 때 validate_all_confirmed가 비어있지 않은 목록을 반환하는지 검증
    - **Validates: Requirements 9.5**

  - [ ]* 11.4 Markdown 라운드트립 Property 테스트 작성
    - **Property 14: Markdown serialization round-trip** — export 후 load한 결과가 원본과 동일한지 검증
    - **Validates: Requirements 10.1, 10.2**

  - [x] 11.5 Markdown 내보내기/로드 REST 엔드포인트 구현
    - `GET /api/documents/{id}/export`: Markdown 파일 다운로드 (Content-Type: text/markdown)
    - `POST /api/documents/import`: Markdown 파일 로드
    - 미확인 객체 경고, 잘못된 Markdown 형식 오류 처리
    - _Requirements: 9.1, 9.5, 10.1, 10.3_

- [x] 12. 백엔드 통합 및 오류 처리
  - [x] 12.1 FastAPI 앱 통합
    - `backend/app/main.py`에 모든 라우터 등록
    - CORS 미들웨어 설정 (프론트엔드 연동)
    - 표준 오류 응답 형식 구현: `{"error": {"code": str, "message": str}}`
    - 전역 예외 핸들러 등록
    - _Requirements: 1.5, 1.6_

  - [ ]* 12.2 백엔드 통합 테스트 작성
    - FastAPI TestClient를 사용한 주요 API 엔드포인트 통합 테스트
    - 업로드 → 노이즈 제거 → 요약 → 내보내기 플로우 테스트
    - _Requirements: 전체_

- [x] 13. Checkpoint - 백엔드 완성 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. 프론트엔드 API 클라이언트 구현
  - [x] 14.1 Axios API 클라이언트 구현
    - `frontend/src/api/client.ts`: 모든 REST API 엔드포인트에 대한 함수 구현
    - 문서 업로드, URL 파싱, 노이즈 제거, 요약 생성, 테이블/이미지 처리, Confirm, JSON 내보내기/로드, API 키 관리
    - 오류 응답 처리 및 Ant Design notification 연동
    - _Requirements: 전체_

- [x] 15. Viewer 컴포넌트 구현
  - [x] 15.1 메인 Viewer 레이아웃 구현
    - `frontend/src/components/Viewer.tsx`: Ant Design Layout + Splitter 사용
    - 좌측: 원본 문서 렌더링 영역
    - 우측: 전처리 결과 객체 목록 렌더링
    - 전처리 작업 후 우측 결과 즉시 갱신
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 15.2 ObjectBox 컴포넌트 구현
    - `frontend/src/components/ObjectBox.tsx`: image/table 객체를 시각적으로 구분하는 카드
    - Confirmed_Status 배지 표시
    - 클릭 시 해당 Processor 패널 열기
    - text 객체는 ObjectBox로 감싸지 않음
    - _Requirements: 1.4, 6.6, 7.7_

  - [ ]* 15.3 ObjectBox 렌더링 Property 테스트 작성 (Jest)
    - **Property 2: Object Box rendering for non-text objects** — image/table 객체만 ObjectBox로 렌더링되고 text 객체는 ObjectBox 없이 렌더링되는지 검증
    - **Validates: Requirements 1.4**

- [x] 16. 문서 업로드 및 노이즈 제거 UI 구현
  - [x] 16.1 문서 업로드 UI 구현
    - Ant Design Upload 컴포넌트로 파일 업로드 (PDF, Word)
    - URL 입력 필드로 웹 페이지 파싱
    - 지원하지 않는 형식 오류 메시지 표시
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [x] 16.2 노이즈 제거 UI 구현
    - 노이즈 제거 버튼 + 커스텀 패턴 입력창 (헤더, 푸터, 페이지 번호)
    - 결과 즉시 Viewer 우측에 반영
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 17. 테이블/이미지 Editor 패널 구현
  - [x] 17.1 TableEditor 패널 구현
    - `frontend/src/components/TableEditor.tsx`
    - pandas 변환 결과 표시, LLM flattening 버튼
    - 텍스트 편집 영역 (읽기 전용/편집 모드 전환)
    - 채팅 입력창 (Ant Design Input.TextArea) + LLM 수정 요청
    - Confirm 버튼
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 17.2 ImageEditor 패널 구현
    - `frontend/src/components/ImageEditor.tsx`
    - "지정 텍스트에 링크로 연결" / "VLM으로 이미지 해석" 옵션 표시
    - VLM 해석 결과 편집 영역 + 채팅 입력창
    - Confirm 버튼
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

- [x] 18. 소제목 요약 및 수동 객체 지정 UI 구현
  - [x] 18.1 소제목 요약 UI 구현
    - 소제목 요약 생성 버튼
    - 수동 소제목 지정 기능 (텍스트 선택 → 소제목 지정)
    - API 키 미등록 시 안내 메시지 표시
    - _Requirements: 4.2, 4.3, 4.4, 4.5_

  - [x] 18.2 수동 객체 지정 UI 구현
    - 수동 테이블 지정 버튼 / 수동 이미지 지정 버튼
    - 문서 영역 선택 후 객체 등록 + ObjectBox 표시
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 19. Settings 패널 및 JSON 내보내기/로드 UI 구현
  - [x] 19.1 Settings 패널 구현
    - `frontend/src/components/Settings.tsx`
    - LLM / VLM API 키 입력 폼
    - 저장 / 검증 버튼
    - _Requirements: 8.1, 8.2, 8.4_

  - [x] 19.2 Markdown 내보내기/로드 UI 구현
    - MD 내보내기 버튼 (파일 다운로드)
    - MD 로드 버튼 (파일 업로드 → 상태 복원)
    - 미확인 객체 경고 메시지 표시
    - 잘못된 Markdown 형식 오류 메시지 표시
    - _Requirements: 9.1, 9.5, 10.1, 10.3_

- [x] 20. 프론트엔드-백엔드 통합 및 최종 검증
  - [x] 20.1 전체 워크플로우 통합 연결
    - 프론트엔드 ↔ 백엔드 API 연동 최종 확인
    - 업로드 → 파싱 → 노이즈 제거 → 요약 → 테이블/이미지 처리 → Confirm → JSON 내보내기 전체 플로우 연결
    - _Requirements: 전체_

  - [ ]* 20.2 프론트엔드 컴포넌트 단위 테스트 작성
    - Jest + React Testing Library로 주요 컴포넌트 렌더링 테스트
    - Viewer, ObjectBox, TableEditor, ImageEditor, Settings 컴포넌트
    - _Requirements: 전체_

- [x] 21. Final Checkpoint - 전체 시스템 검증
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 백엔드는 Python(uv), 프론트엔드는 React + TypeScript(Vite)로 구현
- 최종 출력 포맷은 JSON이 아닌 Markdown(.md)으로, MDExporter가 담당
- Property 테스트는 Hypothesis(백엔드) / Jest(프론트엔드)를 사용
- 각 태스크는 이전 태스크의 결과물 위에 점진적으로 구축됨
- Checkpoint에서 모든 테스트 통과를 확인한 후 다음 단계로 진행
