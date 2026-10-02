@echo off
setlocal
title Stop TrialLens
echo Stopping TrialLens...
rem Only stops a program if it IDENTIFIES as TrialLens. Anything else that happens to
rem use port 8000 or 5173 is left alone.
call :stopport 8000 backend
call :stopport 5173 frontend
echo Done. (You can also just close the two TrialLens windows.)
if /i not "%~1"=="/q" pause
exit /b 0

:stopport
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":%~1  *[^ ]*  *LISTENING"') do (
    set "FOUND=1"
    set "PID=%%p"
)
if "%FOUND%"=="0" (
    echo   Nothing is listening on port %~1.
    exit /b 0
)
if "%~2"=="backend" (
    curl.exe -s -m 3 "http://127.0.0.1:%~1/health" 2>nul | findstr /c:"triallens" >nul
) else (
    curl.exe -s -m 3 "http://localhost:%~1/" 2>nul | findstr /i /c:"TrialLens" >nul
)
if errorlevel 1 (
    echo   Port %~1 is used by a different program - leaving it alone.
    exit /b 0
)
taskkill /PID %PID% /T /F >nul 2>nul
echo   Stopped TrialLens %~2 ^(process %PID%^).
exit /b 0
