@echo off
title StockAI - Push to GitHub
color 0a

echo ========================================================
echo         Pushing StockAI to GitHub Repository
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/4] Configuring remote repository...
git remote remove origin 2>nul
git remote add origin https://github.com/jatothmangilal12-droid/stockai-bot.git

echo [2/4] Staging updated code...
git add .

echo [3/4] Committing updates...
git commit -m "Deploy StockAI Bot with Phase 1-4 complete fixes"

echo [4/4] Pushing to GitHub (main branch)...
git branch -M main
git push -u origin main

echo.
echo ========================================================
if %errorlevel% equ 0 (
    echo SUCCESS! Code successfully pushed to GitHub!
) else (
    echo Notice: If a browser window opened, please complete GitHub sign-in.
)
echo ========================================================
pause
