Write-Output "==> [1/4] Syncing frontend web assets to Android app..."
Copy-Item -Path "frontend\*" -Destination "android_app\www\" -Recurse -Force
Copy-Item -Path "frontend\*" -Destination "android_app\android\app\src\main\assets\public\" -Recurse -Force

Write-Output "==> [2/4] Setting Java Home environment..."
$env:JAVA_HOME = "C:\Program Files\Java\jdk-17"

Write-Output "==> [3/4] Compiling Android APK with Gradle..."
Set-Location "android_app\android"
.\gradlew.bat assembleDebug
Set-Location "..\.."

Write-Output "==> [4/4] Copying compiled APK to root..."
Copy-Item "android_app\android\app\build\outputs\apk\debug\app-debug.apk" "StockAI-bot.apk" -Force

$apk = Get-Item "StockAI-bot.apk"
Write-Output "SUCCESS! New APK built: $($apk.FullName) ($([math]::Round($apk.Length / 1MB, 2)) MB)"
