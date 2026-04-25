@echo off
echo ========================================
echo  Starting SafeDriveVision Backend
echo ========================================
echo.

REM Kill any existing Python processes
echo Stopping any existing backend...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 /nobreak >nul

REM Activate the correct virtual environment
echo Activating virtual environment...
call F:\AlertEye\myenv_311\Scripts\activate.bat

REM Navigate to SafeDriveVision directory
cd /d F:\AlertEye\SafeDriveVision

REM Start the backend server
echo.
echo Starting backend server on http://localhost:8000
echo.
echo ⚠️  KEEP THIS WINDOW OPEN!
echo ⚠️  Press Ctrl+C to stop the server
echo.
echo Waiting for camera to initialize...
echo.

uvicorn app:app --host 0.0.0.0 --port 8000 --log-level info --reload

pause
