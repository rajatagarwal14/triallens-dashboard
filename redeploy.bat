@echo off
setlocal
title TrialLens - Redeploy
cd /d "%~dp0"
echo.
echo   TrialLens - redeploy after local changes
echo   ----------------------------------------
echo   Use this after you edit files in this folder (backend\ or frontend\src\).
echo.
echo   1/3 Stopping TrialLens...
call "%~dp0stop.bat" /q >nul 2>nul
echo   2/3 Saving your edited source to Downloads\TrialLens-source-edited.zip ...
if exist "%USERPROFILE%\Downloads" (
    call "%~dp0package-source.bat" "%USERPROFILE%\Downloads\TrialLens-source-edited.zip"
    if errorlevel 1 (echo       [!] Could not save the zip - continuing anyway.) else (echo       Saved.)
)
echo   3/3 Starting TrialLens with your changes...
echo.
call "%~dp0start.bat"
