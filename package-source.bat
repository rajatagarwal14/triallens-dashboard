@echo off
rem Usage: package-source.bat "C:\path\to\output.zip"
rem Saves ONE zip of the complete project source (backend, frontend, scripts, docs) -
rem without installed packages, caches or downloaded data - so it can be kept as a
rem baseline and redeployed from. Uses tar.exe, which ships with Windows 10/11.
setlocal
set "OUT=%~1"
if "%OUT%"=="" exit /b 1
for %%i in ("%~dp0.") do (
    set "FOLDER=%%~nxi"
    set "PARENT=%%~dpi"
)
tar.exe -a -c -f "%OUT%" -C "%PARENT%" ^
    --exclude=node_modules --exclude=.venv --exclude=.cache --exclude=dist ^
    --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache ^
    "%FOLDER%" >nul 2>nul
exit /b %errorlevel%
