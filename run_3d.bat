@echo off
setlocal
title WARFRONT 3D Launcher

echo ============================================
echo    WARFRONT 3D - Game Launcher
echo ============================================
echo.

python --version >nul 2>&1
if not %errorlevel%==0 (
    echo [ERROR] Python not found. Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
pip install pygame-ce --quiet 2>nul
if not %errorlevel%==0 (
    pip install pygame --quiet 2>nul
)

echo [2/2] Starting game...
echo.
python "%~dp0warfront3d.py"

if not %errorlevel%==0 (
    echo.
    echo [ERROR] Game crashed. Check error messages above.
    pause
)
