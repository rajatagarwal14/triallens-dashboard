@echo off
setlocal enabledelayedexpansion
title TrialLens Setup
cd /d "%~dp0"

echo.
echo   TrialLens - Clinical Intelligence Dashboard
echo   ---------------------------------------------
echo.

set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"

rem --- Find Python (prefer the "py" launcher, fall back to "python") ---
set "PYCMD="
py -3 --version >nul 2>nul
if !errorlevel! equ 0 set "PYCMD=py -3"
if "!PYCMD!"=="" (
    python --version >nul 2>nul
    if !errorlevel! equ 0 set "PYCMD=python"
)
if "!PYCMD!"=="" (
    echo   [!] Python was not found on this computer.
    echo.
    echo   Please install Python 3.9 or newer from:
    echo     https://www.python.org/downloads/
    echo   IMPORTANT: on the first setup screen, check the box
    echo   "Add python.exe to PATH" before clicking Install.
    echo.
    echo   Then double-click start.bat again.
    echo.
    pause
    exit /b 1
)

rem --- Find Node.js ---
node --version >nul 2>nul
if not !errorlevel! equ 0 (
    echo   [!] Node.js was not found on this computer.
    echo.
    echo   Please install the "LTS" version from:
    echo     https://nodejs.org/
    echo.
    echo   Then double-click start.bat again.
    echo.
    pause
    exit /b 1
)

rem --- Backend: create the Python environment on first run only ---
if not exist "%BACKEND%\.venv\Scripts\python.exe" (
    echo   [1/4] Setting up Python environment - first run only, may take a minute...
    !PYCMD! -m venv "%BACKEND%\.venv"
    if errorlevel 1 (
        echo   [!] Could not create the Python environment. See the message above.
        pause
        exit /b 1
    )
)

echo   [2/4] Checking Python packages...
"%BACKEND%\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "%BACKEND%\requirements.txt"
if errorlevel 1 (
    echo   [!] Could not install Python packages.
    echo   Check your internet connection, then double-click start.bat again.
    pause
    exit /b 1
)

rem --- Frontend: install packages on first run only ---
if not exist "%FRONTEND%\node_modules" (
    echo   [3/4] Setting up the dashboard - first run only, may take a minute...
    pushd "%FRONTEND%"
    call npm install --silent
    if errorlevel 1 (
        echo   [!] Could not install dashboard packages.
        echo   Check your internet connection, then double-click start.bat again.
        popd
        pause
        exit /b 1
    )
    popd
)

echo   [4/4] Starting TrialLens...
echo.

rem --- Only launch a server if its port isn't already in use (safe to double-click) ---
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo   Backend is already running.
) else (
    start "" cmd /k call "%~dp0run-backend.bat"
)

netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if !errorlevel! equ 0 (
    echo   Dashboard is already running.
) else (
    start "" cmd /k call "%~dp0run-frontend.bat"
)

echo   Waiting for the dashboard to start...
timeout /t 6 /nobreak >nul

start "" "http://localhost:5173"

echo.
echo   TrialLens is running:
echo     Dashboard  -^> http://localhost:5173
echo     API        -^> http://localhost:8000
echo.
echo   Two windows just opened - one for the backend, one for the dashboard.
echo   To STOP TrialLens: close both of those windows, or run stop.bat.
echo   This window can be closed safely.
echo.
pause
