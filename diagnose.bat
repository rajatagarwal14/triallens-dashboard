@echo off
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
    echo Run start.bat once first so TrialLens can set itself up.
    pause
    exit /b 1
)
"backend\.venv\Scripts\python.exe" diagnose.py
pause
