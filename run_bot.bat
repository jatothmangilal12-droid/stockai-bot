@echo off
title StockAI Bot Launcher
color 0a

echo ========================================================
echo     Starting StockAI Sentiment & 15m Pattern Bot
echo ========================================================
echo.

cd /d "%~dp0"
python run_app.py

pause
