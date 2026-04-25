@echo off
echo ========================================
echo  SafeDriveVision - Driver Monitoring
echo ========================================
echo.

REM Check for virtual environment in project directory
set VENV_ACTIVATE=
if exist "SafeDriveVision\myenv_311\Scripts\activate.bat" (
    set VENV_ACTIVATE=SafeDriveVision\myenv_311\Scripts\activate.bat
) else if exist "F:\SafeDriveVision\myenv_311\Scripts\activate.bat" (
    set VENV_ACTIVATE=F:\SafeDriveVision\myenv_311\Scripts\activate.bat
) else if exist "f:\safedrivevision\myenv_311\Scripts\activate.bat" (
    set VENV_ACTIVATE=f:\safedrivevision\myenv_311\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found!
    pause
    exit /b 1
)

REM Start backend in new window
echo Starting Python Backend...
start "SafeDriveVision Backend" cmd /k "cd /d F:\AlertEye\SafeDriveVision && call %VENV_ACTIVATE% && uvicorn app:app --host 0.0.0.0 --port 8000 --log-level info"

REM Wait longer for backend to fully initialize (YOLO model loading takes time)
echo Waiting for backend to initialize (loading YOLO model)...
timeout /t 20 /nobreak >nul

REM Check if backend is ready
echo Checking backend status...
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo Backend not ready yet, waiting 10 more seconds...
    timeout /t 10 /nobreak >nul
)

REM Start Flutter app
echo Starting Flutter App...
cd /d F:\AlertEye\flutter_app
flutter run -d windows

echo.
echo Application closed.
pause