FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 (PyMuPDF 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# uv 설치
RUN pip install --no-cache-dir uv

# 의존성 설치 (lock 없이 pyproject.toml 기준으로 resolve)
COPY pyproject.toml ./
RUN uv sync --no-dev

# 앱 코드 복사
COPY app/ app/

# 데이터 디렉터리 초기화
RUN mkdir -p images user data

ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000
EXPOSE $PORT

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
