#!/bin/bash
echo "Starting Doc Preprocessing Tool..."

echo "[1/2] Starting Backend (FastAPI)..."
(cd backend && uv run python -m uvicorn app.main:app --port 8000) &

sleep 2

echo "[2/2] Starting Frontend (Vite)..."
(cd frontend && npm run dev) &

echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services."

wait
