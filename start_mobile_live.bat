@echo off
title StockAI - Mobile Live 1-Click Launcher
color 0b

echo ========================================================
echo     StockAI 1-Click Mobile Cloud Link (Cloudflare SSL)
echo ========================================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    python start_tunnel.py
) else (
    if exist "C:\ProgramData\anaconda3\python.exe" (
        "C:\ProgramData\anaconda3\python.exe" start_tunnel.py
    ) else (
        echo Error: Python not found! Please ensure Python or Anaconda is installed.
        pause
    )
)

pause
