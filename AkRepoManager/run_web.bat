@echo off
chcp 65001 >nul
title AkStudio 游戏仓库管理系统 - 调试模式
cd /d "%~dp0"
set PYTHONDONTWRITEBYTECODE=1
set URL=http://127.0.0.1:8765

echo ========================================
echo AkStudio 游戏仓库管理系统 - 调试模式
echo ========================================
echo 地址: %URL%
echo.
echo 正在打开浏览器...
start "" "%URL%"
echo 正在以前台模式启动服务，关闭此窗口会停止服务。
python -u web_server.py 8765

echo.
echo 服务已停止。如果看到错误，请把上面的内容发给我。
pause
