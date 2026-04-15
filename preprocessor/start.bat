@echo off
echo Starting Doc Preprocessing Tool...

echo [1/2] Starting Backend (FastAPI)...
start "Backend" cmd /k "cd /d "%~dp0backend" && uv run python -m uvicorn app.main:app --port 8000"

timeout /t 2 /nobreak > nul

echo [2/2] Starting Frontend (Vite)...
start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
