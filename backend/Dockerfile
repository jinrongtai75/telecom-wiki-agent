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

# HuggingFace 모델 캐시 경로
ENV HF_HOME=/app/data/hf_cache

# .venv의 bin 디렉터리를 PATH에 추가
ENV PATH="/app/.venv/bin:$PATH"

# Railway가 $PORT를 주입, 없으면 8001 fallback
ENV PORT=8001
EXPOSE $PORT

# uvicorn 직접 실행 — 앱은 즉시 시작, 모델은 첫 검색 시 lazy 로딩
# exec: uvicorn이 PID 1이 되어 Railway SIGTERM 정상 처리
# ${PORT:-8001}: Railway가 PORT를 주입하지 않아도 8001로 fallback
CMD ["/bin/sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
