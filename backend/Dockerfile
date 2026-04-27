FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 (PyMuPDF, ChromaDB 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install --no-cache-dir uv

# 의존성 먼저 설치 (레이어 캐싱 활용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 앱 코드 복사
COPY app/ app/

# 데이터 디렉터리 초기화 (볼륨 마운트 전 빈 구조 생성)
RUN mkdir -p data/chroma data/images data/documents data/markdowns

# HuggingFace 모델을 빌드 시 미리 다운로드 (컨테이너 시작 시 지연 제거)
ENV HF_HOME=/app/hf_cache
RUN .venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')"

# .venv의 bin 디렉터리를 PATH에 추가하여 uvicorn을 직접 실행
ENV PATH="/app/.venv/bin:$PATH"

# Railway가 $PORT를 주입, 없으면 8001 fallback
ENV PORT=8001
EXPOSE $PORT

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
