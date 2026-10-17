@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
if not exist .venv\.claimback_dependencies_installed (
    python -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
    type nul > .venv\.claimback_dependencies_installed
)
if not exist .env copy .env.example .env
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
