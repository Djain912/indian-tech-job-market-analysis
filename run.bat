@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
echo.
echo  TechJobs India 2026 running at http://localhost:8000
echo.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
