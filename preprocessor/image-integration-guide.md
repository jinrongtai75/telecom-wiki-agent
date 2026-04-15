# RAG 챗봇 프론트엔드 이미지 연동 가이드

## 1. 개요

이 문서는 전처리 도구로 생성한 `.md` 파일을 RAG 시스템에 학습시킨 후,
챗봇 답변에 이미지를 함께 표시하는 프론트엔드 구현 방법을 설명합니다.

---

## 2. 이미지 경로 포맷 (MD 파일 기준)

전처리 도구가 내보내는 MD 파일에서 이미지 객체는 아래 형식으로 기록됩니다.

```markdown
이미지에 대한 자연어 설명 텍스트 (VLM이 생성한 내용)
<!-- image: /images/obj-a1b2c3d4.png -->
```

- **설명 텍스트**: RAG가 검색·인용하는 실제 컨텍스트
- **`<!-- image: 경로 -->`**: 이미지 파일 경로를 담은 HTML 주석 메타데이터

> 이미지 경로는 전처리 백엔드 서버(`http://localhost:8000`) 기준 정적 파일 경로입니다.

---

## 3. 이미지 서빙 구조

전처리 백엔드는 FastAPI `StaticFiles`로 이미지를 서빙합니다.

```
백엔드 서버: http://localhost:8000
이미지 경로: /images/{filename}
전체 URL:   http://localhost:8000/images/obj-a1b2c3d4.png
```

이미지 파일은 백엔드 서버의 `backend/images/` 폴더에 저장됩니다.
챗봇 프론트엔드에서 이미지를 표시하려면 이 URL로 직접 요청하면 됩니다.

---

## 4. RAG 답변에서 이미지 경로 추출

RAG 시스템이 답변을 생성할 때 MD 파일의 청크를 참조합니다.
답변 또는 참조 청크 텍스트에서 아래 정규식으로 이미지 경로를 추출합니다.

```typescript
// 답변 또는 청크 텍스트에서 이미지 경로 추출
function extractImagePaths(text: string): string[] {
  const regex = /<!--\s*image:\s*(\S+?)\s*-->/g;
  const paths: string[] = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    paths.push(match[1]); // 예: /images/obj-a1b2c3d4.png
  }
  return paths;
}

// 전처리 백엔드 URL로 변환
const PREPROCESSING_BASE_URL = 'http://localhost:8000';

function toImageUrl(imagePath: string): string {
  return `${PREPROCESSING_BASE_URL}${imagePath}`;
}
```

---

## 5. 챗봇 프론트엔드 구현 예시

### 5.1 답변 렌더링 컴포넌트 (React + TypeScript)

```tsx
import React from 'react';

const PREPROCESSING_BASE_URL = 'http://localhost:8000';

// 이미지 경로 추출
function extractImagePaths(text: string): string[] {
  const regex = /<!--\s*image:\s*(\S+?)\s*-->/g;
  const paths: string[] = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    paths.push(match[1]);
  }
  return paths;
}

// 주석 태그 제거 (화면 표시용 텍스트)
function stripImageComments(text: string): string {
  return text.replace(/<!--\s*image:\s*\S+?\s*-->/g, '').trim();
}

interface ChatMessageProps {
  answer: string;       // RAG가 생성한 답변 텍스트
  sources?: string[];   // RAG가 참조한 청크 텍스트 배열 (선택)
}

export default function ChatMessage({ answer, sources = [] }: ChatMessageProps) {
  // 답변 + 참조 청크 전체에서 이미지 경로 수집
  const allText = [answer, ...sources].join('\n');
  const imagePaths = extractImagePaths(allText);

  return (
    <div className="chat-message">
      {/* 텍스트 답변 */}
      <p style={{ whiteSpace: 'pre-wrap' }}>
        {stripImageComments(answer)}
      </p>

      {/* 이미지 표시 */}
      {imagePaths.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 12 }}>
          {imagePaths.map((path) => (
            <img
              key={path}
              src={`${PREPROCESSING_BASE_URL}${path}`}
              alt={path}
              style={{ maxWidth: 480, borderRadius: 8, border: '1px solid #e8e8e8' }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

### 5.2 사용 예시

```tsx
// RAG API 응답 예시
const ragResponse = {
  answer: "5G IoT 네트워크 품질 모니터링은 패킷 Tapping 방식을 사용합니다.\n<!-- image: /images/obj-a1b2c3d4.png -->",
  source_chunks: [
    "ToR_SW에서 품질 패킷을 미러링하여 5G Probe로 전달합니다.\n<!-- image: /images/obj-a1b2c3d4.png -->"
  ]
};

// 렌더링
<ChatMessage
  answer={ragResponse.answer}
  sources={ragResponse.source_chunks}
/>
```

---

## 6. RAG 시스템 연동 시 권장 사항

### 6.1 청크 분리 전략

MD 파일을 RAG에 학습시킬 때 `<!-- image: ... -->` 주석을 **청크에서 제거하지 말고 유지**하세요.

```python
# ✅ 권장: 주석 포함 그대로 청크화
chunk = "5G 모니터링 아키텍처 설명...\n<!-- image: /images/obj-a1b2c3d4.png -->"

# ❌ 비권장: 주석 제거 후 청크화 (이미지 연결 정보 소실)
chunk = "5G 모니터링 아키텍처 설명..."
```

### 6.2 메타데이터로 이미지 경로 별도 저장

벡터 DB에 청크를 저장할 때 이미지 경로를 메타데이터로 분리 저장하면
검색 후 이미지 경로를 더 쉽게 활용할 수 있습니다.

```python
import re

def parse_chunk_with_image(chunk_text: str) -> dict:
    image_paths = re.findall(r'<!--\s*image:\s*(\S+?)\s*-->', chunk_text)
    clean_text = re.sub(r'<!--\s*image:\s*\S+?\s*-->', '', chunk_text).strip()
    return {
        "text": clean_text,           # 벡터 임베딩에 사용할 텍스트
        "metadata": {
            "image_paths": image_paths  # 벡터 DB 메타데이터로 저장
        }
    }

# 벡터 DB 저장 예시 (LangChain 기준)
from langchain.schema import Document

doc = Document(
    page_content=parsed["text"],
    metadata=parsed["metadata"]
)
```

### 6.3 검색 결과에서 이미지 경로 복원

```python
# 검색 결과에서 이미지 경로 추출
results = vector_db.similarity_search(query, k=3)

image_paths = []
for result in results:
    paths = result.metadata.get("image_paths", [])
    image_paths.extend(paths)

# 중복 제거
image_paths = list(dict.fromkeys(image_paths))
```

---

## 7. CORS 설정 확인

챗봇 프론트엔드가 전처리 백엔드(`localhost:8000`)의 이미지를 직접 요청하는 경우,
백엔드의 CORS 허용 origin에 챗봇 프론트엔드 주소가 포함되어야 합니다.

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # 전처리 도구 프론트엔드
        "http://localhost:3000",   # 챗봇 프론트엔드 (추가 필요)
    ],
    ...
)
```

---

## 8. 프로덕션 배포 시 고려사항

로컬 개발 환경이 아닌 실제 배포 환경에서는 아래를 고려하세요.

| 항목 | 권장 방법 |
|------|----------|
| 이미지 파일 공유 | `backend/images/` 폴더를 공유 스토리지(NAS, S3 등)로 교체 |
| 이미지 URL | `http://localhost:8000` 대신 실제 서버 도메인으로 변경 |
| 경로 일관성 | MD 파일 내 `/images/파일명` 형식은 유지, base URL만 환경변수로 관리 |

```typescript
// 환경변수로 base URL 관리
const PREPROCESSING_BASE_URL = process.env.NEXT_PUBLIC_PREPROCESSING_URL ?? 'http://localhost:8000';
```
