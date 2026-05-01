#!/bin/sh
set -e
exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}"
