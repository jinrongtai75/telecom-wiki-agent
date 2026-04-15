FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 (PyMuPDF, ChromaDB 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install --no-cache-dir uv

# 의존성 먼저 설치 (레이어 캐싱 활용)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# 앱 코드 복사
COPY app/ app/

# 데이터 디렉터리 초기화 (볼륨 마운트 전 빈 구조 생성)
RUN mkdir -p data/chroma data/images data/documents data/markdowns

# HuggingFace 모델 캐시를 볼륨 내부에 저장
ENV HF_HOME=/app/data/hf_cache

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
