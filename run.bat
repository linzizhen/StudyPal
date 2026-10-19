@echo off
chcp 65001 >nul
title StudyPal 启动

rem 切换到本脚本所在目录，避免硬编码路径
cd /d "%~dp0"

echo [1/3] 清理占用 5000 端口的旧进程...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000 ^| findstr LISTENING') do (
    echo   杀掉 PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo [2/3] 选择 Python 解释器...
set "PY="
if exist ".\.venv\Scripts\python.exe" (
    set "PY=.\.venv\Scripts\python.exe"
    echo   使用虚拟环境 .venv
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [错误] 未找到 Python。
        echo   请先安装 Python，或在项目根目录创建 .venv 虚拟环境：
        echo     python -m venv .venv
        echo     .venv\Scripts\pip install -r requirements.txt
        pause
        exit /b 1
    )
    set "PY=python"
    echo   未找到 .venv，使用系统 python
)

echo [3/3] 启动 Flask...
echo   访问 http://localhost:5000
echo.
"%PY%" app.py
pause
