#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "무선통신프로토콜 위키백과사전 에이전트 시작"

# .env 파일 확인
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
    echo "  backend/.env 파일이 없습니다. .env.example을 복사하세요:"
    echo "   cp .env.example backend/.env"
    echo "   그 후 JWT_SECRET 등을 수정하세요."
    exit 1
fi

# 관리자 계정 초기화 (DB에 admin 없을 때만)
cd "$SCRIPT_DIR/backend"
ADMIN_COUNT=$(uv run python3 -c "
from app.database import SessionLocal, create_tables
from app.models.db_models import User
create_tables()
db = SessionLocal()
n = db.query(User).filter(User.is_admin == True).count()
db.close()
print(n)
" 2>/dev/null || echo "0")

if [ "$ADMIN_COUNT" = "0" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  최초 실행: 관리자 계정을 생성합니다"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    uv run python scripts/create_admin.py
    echo ""
fi

# [1/4] 전처리 도구 백엔드 (포트 8000)
echo "[1/4] 전처리 도구 백엔드 시작 (포트 8000)..."
cd "$SCRIPT_DIR/preprocessor/backend"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
PREP_BACKEND_PID=$!

# [2/4] Wiki Agent 백엔드 (포트 8001)
echo "[2/4] Wiki Agent 백엔드 시작 (포트 8001)..."
cd "$SCRIPT_DIR/backend"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 &
WIKI_BACKEND_PID=$!

# 백엔드 헬스체크 대기
echo "⏳ 백엔드 준비 대기 중..."
for i in $(seq 1 30); do
    PREP_OK=false
    WIKI_OK=false
    curl -s http://localhost:8000/health > /dev/null 2>&1 && PREP_OK=true
    curl -s http://localhost:8001/api/health > /dev/null 2>&1 && WIKI_OK=true
    if $PREP_OK && $WIKI_OK; then
        echo "✅ 백엔드 준비 완료"
        break
    fi
    sleep 1
done

# [3/4] 전처리 도구 프론트엔드 (포트 1024)
echo "[3/4] 전처리 도구 프론트엔드 시작 (포트 1024)..."
cd "$SCRIPT_DIR/preprocessor/frontend"
npm run dev -- --port 1024 &
PREP_FRONTEND_PID=$!

# [4/4] Wiki Agent 프론트엔드 (포트 5173)
echo "[4/4] Wiki Agent 프론트엔드 시작 (포트 5173)..."
cd "$SCRIPT_DIR/frontend"
npm run dev &
WIKI_FRONTEND_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [전처리 도구]"
echo "    프론트엔드:  http://localhost:1024"
echo "    백엔드:      http://localhost:8000"
echo "    API 문서:    http://localhost:8000/docs"
echo ""
echo "  [Wiki Agent]"
echo "    프론트엔드:  http://localhost:5173"
echo "    백엔드:      http://localhost:8001"
echo "    API 문서:    http://localhost:8001/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Ctrl+C 로 종료"
echo ""

trap "kill $PREP_BACKEND_PID $WIKI_BACKEND_PID $PREP_FRONTEND_PID $WIKI_FRONTEND_PID 2>/dev/null; exit" INT TERM EXIT
wait $WIKI_BACKEND_PID
