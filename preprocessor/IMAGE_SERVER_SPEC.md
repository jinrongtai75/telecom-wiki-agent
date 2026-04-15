# 이미지 서버 연동 규격서

## 개요

문서 전처리 도구에서 추출된 이미지를 별도 이미지 서버에 저장하고,
RAG 파이프라인에서 이미지 경로를 메타데이터로 활용하기 위한 연동 규격입니다.

---

## 현재 아키텍처 (로컬)

```
[전처리 도구] --저장--> [로컬 /images 디렉토리]
                              |
                    image_path: /images/obj-xxx.png
                              |
              [MD 파일] ![alt](/images/obj-xxx.png)
```

---

## 목표 아키텍처 (프로덕션)

```
[전처리 도구] --업로드--> [이미지 서버 (S3 / NFS / 자체 서버)]
                                    |
                        image_path: https://images.example.com/docs/obj-xxx.png
                                    |
                    [MD 파일] ![패킷 포맷](https://images.example.com/docs/obj-xxx.png)
                                    |
              [벡터 DB] { text: "...", metadata: { image_url: "https://..." } }
                                    |
                    [RAG 답변] 텍스트 + 이미지 URL 반환
```

---

## 이미지 서버 API 규격

### 1. 이미지 업로드

```
POST /images/upload
Content-Type: multipart/form-data

Fields:
  - file: 이미지 파일 (png, jpg, jpeg, gif, webp)
  - doc_id: 문서 ID (string) — 이미지가 속한 문서
  - obj_id: 객체 ID (string) — 예: obj-930d96b5

Response 200:
{
  "image_url": "https://images.example.com/docs/obj-930d96b5.png",
  "image_id": "obj-930d96b5",
  "doc_id": "...",
  "size": 204800
}

Response 400:
{
  "error": "지원하지 않는 파일 형식입니다"
}
```

### 2. 이미지 조회

```
GET /images/{image_id}

Response 200: 이미지 파일 (Content-Type: image/png 등)
Response 404: { "error": "이미지를 찾을 수 없습니다" }
```

### 3. 이미지 삭제

```
DELETE /images/{image_id}
Authorization: Bearer {api_key}

Response 200: { "deleted": true }
Response 404: { "error": "이미지를 찾을 수 없습니다" }
```

### 4. 문서 이미지 목록 조회

```
GET /images?doc_id={doc_id}

Response 200:
{
  "images": [
    {
      "image_id": "obj-930d96b5",
      "image_url": "https://images.example.com/docs/obj-930d96b5.png",
      "doc_id": "...",
      "created_at": "2026-03-27T00:00:00Z"
    }
  ]
}
```

---

## 전처리 도구 연동 포인트

### 현재 코드 위치

`backend/app/modules/image_processor.py` — `save_and_link()` 메서드

```python
# 현재: 로컬 저장
filepath = save_path / filename
filepath.write_bytes(base64.b64decode(b64data))
image_path = f"/images/{filename}"

# 변경: 이미지 서버 업로드
response = httpx.post(
    f"{IMAGE_SERVER_URL}/images/upload",
    files={"file": (filename, base64.b64decode(b64data), f"image/{ext}")},
    data={"doc_id": doc_id, "obj_id": image_object.id},
    headers={"Authorization": f"Bearer {IMAGE_SERVER_API_KEY}"},
)
image_path = response.json()["image_url"]
```

### 환경 변수 추가 (배포 시)

```env
IMAGE_SERVER_URL=https://images.example.com
IMAGE_SERVER_API_KEY=your_api_key_here
```

`backend/app/modules/api_key_manager.py` 또는 `.env` 파일에 추가합니다.

---

## MD 파일 출력 형태

이미지 연결(지정 텍스트에 링크) 처리 후 MD 내보내기 시:

```markdown
![패킷 포맷](https://images.example.com/docs/obj-930d96b5.png)
```

- **alt 텍스트**: 사용자가 지정한 연결 텍스트 (예: "패킷 포맷")
- **URL**: 이미지 서버의 퍼블릭 URL

---

## RAG 파이프라인 연동

### 청크 분리 전략

MD 파일을 청크로 분리할 때 이미지 라인을 만나면:

```python
# 이미지 라인 감지
import re
IMAGE_RE = re.compile(r'!\[(.+?)\]\((.+?)\)')

def parse_chunk(line):
    m = IMAGE_RE.match(line)
    if m:
        return {
            "type": "image_ref",
            "alt": m.group(1),       # "패킷 포맷"
            "image_url": m.group(2), # "https://images.example.com/..."
        }
    return {"type": "text", "content": line}
```

### 벡터 DB 저장 형태 (예: Chroma / Pinecone)

```python
collection.add(
    documents=["패킷 포맷"],          # alt 텍스트를 텍스트로 인덱싱
    metadatas=[{
        "image_url": "https://images.example.com/docs/obj-930d96b5.png",
        "doc_id": "...",
        "type": "image"
    }],
    ids=["obj-930d96b5"]
)
```

### RAG 답변 시 이미지 반환

```python
results = collection.query(query_texts=["패킷 포맷 설명해줘"], n_results=5)

for result in results:
    if result["metadata"].get("type") == "image":
        image_url = result["metadata"]["image_url"]
        # 답변에 이미지 URL 포함하여 프론트엔드에 전달
        response["images"].append(image_url)
```

---

## 배포 체크리스트

- [ ] 이미지 서버 구축 (S3 버킷 / 자체 서버)
- [ ] `IMAGE_SERVER_URL`, `IMAGE_SERVER_API_KEY` 환경 변수 설정
- [ ] `image_processor.py`의 `save_and_link()` 로컬 저장 → 서버 업로드로 교체
- [ ] 이미지 서버 CORS 설정 (프론트엔드 도메인 허용)
- [ ] 이미지 URL이 외부에서 접근 가능한지 확인 (퍼블릭 URL)
- [ ] RAG 파이프라인에서 이미지 메타데이터 인덱싱 로직 추가
