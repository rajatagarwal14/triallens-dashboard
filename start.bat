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

rem --- Is winget available? (built into Windows 10 2004+ / Windows 11 —
rem     lets us install Python/Node ourselves instead of sending the user to
rem     a browser. If it's missing, we just fall back to the manual links.) ---
set "HAVE_WINGET=0"
winget --version >nul 2>nul
if !errorlevel! equ 0 set "HAVE_WINGET=1"

rem --- Find Python (prefer the "py" launcher, fall back to "python") ---
set "PYCMD="
py -3 --version >nul 2>nul
if !errorlevel! equ 0 set "PYCMD=py -3"
if "!PYCMD!"=="" (
    python --version >nul 2>nul
    if !errorlevel! equ 0 set "PYCMD=python"
)
set "NEED_RESTART=0"
if "!PYCMD!"=="" (
    if "!HAVE_WINGET!"=="1" (
        echo   Python was not found - installing it now via winget...
        echo   ^(this is silent and does not need a browser^)
        winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        if !errorlevel! equ 0 (
            set "NEED_RESTART=1"
        ) else (
            echo   [!] Automatic install did not complete.
            echo.
            echo   Please install Python 3.9 or newer yourself from:
            echo     https://www.python.org/downloads/
            echo   IMPORTANT: on the first setup screen, check the box
            echo   "Add python.exe to PATH" before clicking Install.
            echo.
            echo   Then double-click start.bat again.
            echo.
            pause
            exit /b 1
        )
    ) else (
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
)

rem --- Find Node.js ---
node --version >nul 2>nul
if not !errorlevel! equ 0 (
    if "!HAVE_WINGET!"=="1" (
        echo   Node.js was not found - installing it now via winget...
        echo   ^(this may ask you to approve an admin prompt - that's normal^)
        winget install -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        if !errorlevel! equ 0 (
            set "NEED_RESTART=1"
        ) else (
            echo   [!] Automatic install did not complete - it likely needs an
            echo   administrator on this computer to approve it.
            echo.
            echo   Please install the "LTS" version yourself from:
            echo     https://nodejs.org/
            echo.
            echo   Then double-click start.bat again.
            echo.
            pause
            exit /b 1
        )
    ) else (
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
)

rem --- The dashboard's build tool needs Node 20.19+ (or 22.12+). An older Node installs
rem     fine but then fails in confusing ways, so check it here and say so plainly. ---
if "!NEED_RESTART!"=="0" (
    node -e "const [a,b]=process.versions.node.split('.').map(Number);process.exit((a>22||(a===22&&b>=12)||(a===20&&b>=19))?0:1)" >nul 2>nul
    if errorlevel 1 (
        echo   [!] Your Node.js is too old. TrialLens needs Node 20.19 or newer.
        if "!HAVE_WINGET!"=="1" (
            echo   Updating Node.js via winget...
            winget upgrade -e --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
            if !errorlevel! equ 0 (
                echo.
                echo   Node.js was updated. Please close this window and double-click start.bat again.
                pause
                exit /b 0
            )
        )
        echo.
        echo   Please install the current "LTS" version from https://nodejs.org/
        echo   ^(or ask IT to update Node.js^), then double-click start.bat again.
        echo.
        pause
        exit /b 1
    )
)

rem --- Windows doesn't give a freshly-installed program's PATH to this
rem     already-running window. Rather than risk getting that wrong, ask for
rem     one more double-click - everything from here on is fully automatic. ---
if "!NEED_RESTART!"=="1" (
    echo.
    echo   Setup installed the required program^(s^).
    echo   Please close this window and double-click start.bat one more time
    echo   to finish - everything after this is automatic.
    echo.
    pause
    exit /b 0
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

rem --- Install/refresh packages ONLY when the dependency list changed since last time.
rem     (Previously the frontend was installed once and never refreshed after an update.) ---
call :hashof "%BACKEND%\requirements.txt" REQ_HASH
set "REQ_OLD="
if exist "%BACKEND%\.venv\.requirements.sha" set /p REQ_OLD=<"%BACKEND%\.venv\.requirements.sha"
if not "!REQ_HASH!"=="!REQ_OLD!" (
    echo   [2/4] Installing Python packages...
    "%BACKEND%\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo   [!] Could not install Python packages.
        echo   Check your internet connection ^(or ask IT about the Python package index^),
        echo   then double-click start.bat again. diagnose.bat can help find the cause.
        pause
        exit /b 1
    )
    >"%BACKEND%\.venv\.requirements.sha" echo !REQ_HASH!
) else (
    echo   [2/4] Python packages are up to date.
)

call :hashof "%FRONTEND%\package-lock.json" LOCK_HASH
set "LOCK_OLD="
if exist "%FRONTEND%\node_modules\.triallens-lock.sha" set /p LOCK_OLD=<"%FRONTEND%\node_modules\.triallens-lock.sha"
if not exist "%FRONTEND%\node_modules" set "LOCK_OLD="
if not "!LOCK_HASH!"=="!LOCK_OLD!" (
    echo   [3/4] Installing dashboard packages - may take a minute...
    pushd "%FRONTEND%"
    call npm ci --no-audit --no-fund --silent
    if errorlevel 1 (
        echo   [!] Could not install dashboard packages.
        echo   Check your internet connection ^(or ask IT about the npm registry^),
        echo   then double-click start.bat again.
        popd
        pause
        exit /b 1
    )
    popd
    >"%FRONTEND%\node_modules\.triallens-lock.sha" echo !LOCK_HASH!
) else (
    echo   [3/4] Dashboard packages are up to date.
)

echo   [4/4] Starting TrialLens...
echo.

rem --- Never assume whatever is listening on a port is TrialLens. Check what it is. ---
call :probe 8000 backend
if "!PORT_STATE!"=="triallens" (
    echo   Backend is already running.
) else if "!PORT_STATE!"=="other" (
    echo   [!] Port 8000 is being used by another program, not TrialLens.
    echo       Close that program ^(or ask IT what it is^) and run start.bat again.
    echo       TrialLens did not touch it.
    pause
    exit /b 1
) else (
    start "TrialLens Backend" cmd /k call "%~dp0run-backend.bat"
)

call :probe 5173 frontend
if "!PORT_STATE!"=="triallens" (
    echo   Dashboard is already running.
) else if "!PORT_STATE!"=="other" (
    echo   [!] Port 5173 is being used by another program, not TrialLens.
    echo       Close that program and run start.bat again. TrialLens did not touch it.
    pause
    exit /b 1
) else (
    start "TrialLens Dashboard" cmd /k call "%~dp0run-frontend.bat"
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
exit /b 0

rem ---------------------------------------------------------------------------
rem :hashof <file> <varname>   SHA-256 of a file, via certutil (built into Windows)
:hashof
set "%~2="
rem Pick the hex line itself (works on any Windows display language).
for /f "delims=" %%h in ('certutil -hashfile "%~1" SHA256 2^>nul ^| findstr /r /i /c:"^[0-9a-f][0-9a-f ]*$"') do (
    if not defined %~2 set "%~2=%%h"
)
exit /b 0

rem :probe <port> <backend|frontend>   sets PORT_STATE to free / triallens / other
rem Uses netstat + curl.exe (both ship with Windows 10/11); no PowerShell needed.
:probe
set "PORT_STATE=free"
netstat -ano | findstr /r /c:":%~1  *[^ ]*  *LISTENING" >nul
if errorlevel 1 exit /b 0
set "PORT_STATE=other"
if "%~2"=="backend" (
    curl.exe -s -m 3 "http://127.0.0.1:%~1/health" 2>nul | findstr /c:"triallens" >nul
) else (
    curl.exe -s -m 3 "http://127.0.0.1:%~1/" 2>nul | findstr /i /c:"TrialLens" >nul
)
if not errorlevel 1 set "PORT_STATE=triallens"
exit /b 0
