@echo off
chcp 65001 >nul
title 启动 AkStudio 游戏仓库管理系统
cd /d "E:\AkStudio\AkRepoManager"
set PYTHONDONTWRITEBYTECODE=1
set URL=http://127.0.0.1:8765

echo 正在启动 AkStudio 游戏仓库管理系统...

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing '%URL%/api/scan' -TimeoutSec 1; if($r.StatusCode -eq 200){ exit 0 } else { exit 1 } } catch { exit 1 }"
if ERRORLEVEL 1 (
    echo 服务未运行，正在后台启动...
    start "AkStudioRepoManagerServer" /min cmd /c "cd /d E:\AkStudio\AkRepoManager && set PYTHONDONTWRITEBYTECODE=1 && python -u web_server.py 8765 >> server.out.log 2>> server.err.log"
    timeout /t 2 /nobreak >nul
) else (
    echo 服务已经在运行。
)

echo 正在打开浏览器: %URL%
start "" "%URL%"

echo 如果没有自动打开，请手动复制访问: %URL%
timeout /t 3 /nobreak >nul
exit /b 0
