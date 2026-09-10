@echo off
title TrialLens Dashboard - close this window to stop it
cd /d "%~dp0frontend"
call npm run dev
pause
