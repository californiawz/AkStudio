@echo off
chcp 65001 >nul
title AkStudio Portal
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
set URL=http://127.0.0.1:8750
start "" "%URL%"
python -u portal_server.py 8750
pause
