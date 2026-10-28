Write-Output "==> [1/4] Syncing frontend web assets to Android app..."
Copy-Item -Path "frontend\*" -Destination "android_app\www\" -Recurse -Force
Copy-Item -Path "frontend\*" -Destination "android_app\android\app\src\main\assets\public\" -Recurse -Force

Write-Output "==> [2/4] Setting Java Home environment..."
$env:JAVA_HOME = "C:\Program Files\Java\jdk-17"

# Clean old APK to guarantee fresh build
if (Test-Path "StockAI-bot.apk") {
    Remove-Item "StockAI-bot.apk" -Force
}
if (Test-Path "android_app\android\app\build\outputs\apk\debug\app-debug.apk") {
    Remove-Item "android_app\android\app\build\outputs\apk\debug\app-debug.apk" -Force
}

Write-Output "==> [3/4] Compiling fresh Android APK with Gradle..."
Set-Location "android_app\android"
.\gradlew.bat clean assembleDebug
Set-Location "..\.."

Write-Output "==> [4/4] Copying freshly compiled APK to root..."
Copy-Item "android_app\android\app\build\outputs\apk\debug\app-debug.apk" "StockAI-bot.apk" -Force

$apk = Get-Item "StockAI-bot.apk"
Write-Output "SUCCESS! Brand new APK built: $($apk.FullName) ($([math]::Round($apk.Length / 1MB, 2)) MB) - Timestamp: $($apk.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
