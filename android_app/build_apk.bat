@echo off
title StockAI - Android APK Builder
echo ========================================================
echo         StockAI Android APK Build Assistant
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/4] Checking Node.js and NPM...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Node.js is not found on your system. Please install Node.js from https://nodejs.org/
    pause
    exit /b
)

echo [2/4] Installing Capacitor Android dependencies...
call npm install

echo [3/4] Initializing / Syncing Android platform...
if not exist "android" (
    call npx cap add android
)
call npx cap sync android

echo.
echo [4/4] Building APK via Gradle...
if exist "android\gradlew.bat" (
    cd android
    call gradlew.bat assembleDebug
    echo.
    echo ========================================================
    echo SUCCESS! Your Android APK is compiled:
    echo Location: android\app\build\outputs\apk\debug\app-debug.apk
    echo ========================================================
) else (
    echo Opening Android Studio for 1-click build...
    call npx cap open android
)

echo.
pause
