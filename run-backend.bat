@echo off
title TrialLens Backend - close this window to stop it
cd /d "%~dp0backend"
if not exist ".venv\Scripts\python.exe" (
    echo Backend environment not found. Please run start.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
