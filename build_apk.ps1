$env:JAVA_HOME = "C:\Program Files\Java\jdk-17"
Set-Location "android_app\android"
.\gradlew.bat assembleDebug
Set-Location "..\.."
Copy-Item "android_app\android\app\build\outputs\apk\debug\app-debug.apk" "StockAI-bot.apk" -Force
Write-Output "APK built and copied to StockAI-bot.apk successfully!"
