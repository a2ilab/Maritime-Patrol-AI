@echo off
chcp 65001 >nul
echo === Maritime Patrol AI 서버 시작 ===
echo.
echo API 서버: http://127.0.0.1:8000
echo Map Viewer: http://127.0.0.1:8502
echo.
echo 두 개의 창이 열립니다. 각각 닫지 마세요.
echo.
start "API Server (8000)" cmd /k "cd /d D:\Git\Maritime-Patrol-AI-master && py api.py"
timeout /t 2 /nobreak >nul
start "Map Viewer (8502)" cmd /k "cd /d D:\Git\Maritime-Patrol-AI-master\map-viewer && py run.py"
echo.
echo 서버가 시작되었습니다.
echo 브라우저에서 http://127.0.0.1:8502 접속
pause
