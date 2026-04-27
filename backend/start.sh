#!/bin/sh
# 모델이 캐시에 없으면 다운로드 후 uvicorn 시작
echo "=== HuggingFace 모델 확인 중 ==="
.venv/bin/python -c "
from sentence_transformers import SentenceTransformer
print('모델 로딩 중...')
SentenceTransformer('intfloat/multilingual-e5-large')
print('모델 준비 완료')
"
echo "=== uvicorn 시작 ==="
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
