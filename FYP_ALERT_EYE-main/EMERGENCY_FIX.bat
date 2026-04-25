@echo off
echo ========================================
echo  EMERGENCY FIX - Killing all processes
echo ========================================
echo.

echo Stopping all Python processes...
taskkill /F /IM python.exe /T 2>nul

echo Stopping Flutter app...
taskkill /F /IM flutter_application_1.exe /T 2>nul

echo.
echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  All processes stopped!
echo ========================================
echo.
echo Now run these commands in ORDER:
echo.
echo 1. In Window 1: .\START_BACKEND_ONLY.bat
echo 2. Wait for "Uvicorn running"
echo 3. In Window 2: cd flutter_app
echo 4. In Window 2: .\run_mobile.bat
echo.
pause
