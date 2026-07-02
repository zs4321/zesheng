@echo off
setlocal
title WARFRONT 3D - Build EXE

echo ============================================
echo    WARFRONT 3D - EXE Builder
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

echo [1/3] Installing dependencies...
pip install pygame-ce --quiet 2>nul
if not %errorlevel%==0 (
    pip install pygame --quiet 2>nul
)
pip install pyinstaller --quiet
if not %errorlevel%==0 (
    echo [ERROR] Install failed.
    pause
    exit /b 1
)

echo [2/3] Building EXE...
echo.

cd /d "%~dp0"

pyinstaller --onefile --noconsole --name WARFRONT3D --clean warfront3d.py

echo.
if exist "dist\WARFRONT3D.exe" (
    echo ============================================
    echo  [3/3] Build successful!
    echo  EXE location: dist\WARFRONT3D.exe
    echo ============================================
    echo.
    explorer "dist"
) else (
    echo [ERROR] Build failed. Check error messages above.
)

echo.
pause
