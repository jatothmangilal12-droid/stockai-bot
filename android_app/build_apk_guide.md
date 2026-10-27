# 📱 StockAI Android App (APK) Complete Guide

Mowa, ee application ni nee Android Mobile lo run cheyadaniki 2 super easy methods unnayi:

---

## 🚀 Method 1: Instant PWA Mobile App (Zero Setup - Recommended)
Neeku Android Studio lekunna sare, 10 seconds lo nee phone lo standalone app laga install chesukovachu:

1. **PC lo Server Start cheyyi**:
   - `run_bot.bat` meeda double click cheyyi (or run `python run_app.py`).
2. **Nee PC Local IP Address kanukko**:
   - Command Prompt lo `ipconfig` type cheyyi (e.g. `192.168.1.15`).
3. **Nee Android Phone lo Chrome Open cheyyi**:
   - Browser URL lo `http://<NEE_PC_IP>:8000` ani enter cheyyi (e.g., `http://192.168.1.15:8000`).
   - (Note: Phone mariyu PC rendu same Wi-Fi / Hotspot lo undali).
4. **App Install Cheyyi**:
   - Chrome top-right 3 dots (⋮) tap cheyyi.
   - **"Install app"** or **"Add to Home screen"** select cheyyi.
   - App logo tho nee phone home screen meeda standalone APK laga install aipotundi! Full screen lo open avtundi!

---

## 📦 Method 2: Native Android APK (.apk) File Compile Cheyadam

Nuvvu direct ga `.apk` file create chesi phone lo install cheskovali anukunte:

### Pre-requisites:
- Node.js (already installed)
- Java JDK 17 (already installed)
- Android Studio / Android SDK

### Steps to Compile APK:
1. `android_app` folder lo unna **`build_apk.bat`** file ni double-click chesi run cheyyi.
2. Idi automatically:
   - Capacitor CLI & Android platform ni initialize chestundi.
   - Gradle tho build process run chestundi.
3. Build complete ayyaka nee APK file ikkada create avtundi:
   ```
   android_app/android/app/build/outputs/apk/debug/app-debug.apk
   ```
4. Ee `app-debug.apk` file ni nee phone ki WhatsApp/USB/Drive dwara transfer chesi install chesukovachu!
