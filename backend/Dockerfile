FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 (PyMuPDF, ChromaDB 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install --no-cache-dir uv

# 의존성 먼저 설치 (레이어 캐싱 활용) — cache-bust: 2026-05-01
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 앱 코드 복사
COPY app/ app/

# 데이터 디렉터리 초기화 (볼륨 마운트 전 빈 구조 생성)
RUN mkdir -p data/chroma data/images data/documents data/markdowns

# ChromaDB ONNX 번들 모델 사전 로딩 (onnxruntime 초기화)
RUN /app/.venv/bin/python -c "from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2; ONNXMiniLM_L6_V2()"

# .venv의 bin 디렉터리를 PATH에 추가
ENV PATH="/app/.venv/bin:$PATH"

# Railway가 $PORT를 주입, 없으면 8001 fallback
ENV PORT=8001
EXPOSE $PORT

# startup script 복사 후 실행 권한 부여
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# start.sh가 PORT 환경변수를 shell에서 직접 치환 (Railway $PORT 주입 호환)
CMD ["/app/start.sh"]
