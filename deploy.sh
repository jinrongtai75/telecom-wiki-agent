#!/usr/bin/env bash
# Oracle Cloud VM 초기 배포 스크립트
# 사용법: bash deploy.sh
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  텔레콤 위키 에이전트 — Oracle VM 배포"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Docker 설치 확인 ────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "[1/5] Docker 설치 중..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "✅ Docker 설치 완료 (재로그인 필요할 수 있음)"
else
    echo "[1/5] Docker 이미 설치됨 ✅"
fi

# ── 2. Docker Compose 설치 확인 ───────────────────────────────────────────
if ! command -v docker compose &> /dev/null; then
    echo "[2/5] Docker Compose 설치 중..."
    sudo apt-get update -qq
    sudo apt-get install -y docker-compose-plugin
    echo "✅ Docker Compose 설치 완료"
else
    echo "[2/5] Docker Compose 이미 설치됨 ✅"
fi

# ── 3. .env 파일 확인 ─────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "[3/5] .env 파일 생성 중..."
    cp .env.example .env
    echo ""
    echo "⚠️  .env 파일을 편집하세요:"
    echo "   nano .env"
    echo ""
    echo "   필수 항목:"
    echo "   - JWT_SECRET (32자 이상 랜덤 문자열)"
    echo "   - CORS_ORIGINS (Vercel 프론트엔드 URL)"
    echo ""
    read -p "편집 완료 후 Enter를 누르세요..."
else
    echo "[3/5] .env 파일 존재 ✅"
fi

# ── 4. 방화벽 포트 오픈 (Oracle Cloud는 iptables도 설정 필요) ─────────────
echo "[4/5] 방화벽 설정 중..."
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 8001 -j ACCEPT
# 재부팅 후에도 유지
sudo apt-get install -y iptables-persistent -qq 2>/dev/null || true
sudo netfilter-persistent save 2>/dev/null || true
echo "✅ 방화벽 설정 완료"

# ── 5. Docker Compose 빌드 & 실행 ─────────────────────────────────────────
echo "[5/5] 서비스 빌드 및 시작 중... (첫 빌드는 10~20분 소요)"
sudo docker compose pull 2>/dev/null || true
sudo docker compose up -d --build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  배포 완료!"
echo ""
echo "  Wiki 백엔드:  http://$(curl -s ifconfig.me):8001"
echo "  전처리 백엔드: http://$(curl -s ifconfig.me):8000"
echo "  Nginx:        http://$(curl -s ifconfig.me)"
echo ""
echo "  로그 확인: sudo docker compose logs -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
