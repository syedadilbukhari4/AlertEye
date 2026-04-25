@echo off
echo ========================================
echo  SafeDriveVision - Installation Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.11 from https://www.python.org/
    pause
    exit /b 1
)

REM Create virtual environment
echo [1/5] Creating Python virtual environment...
cd /d F:\AlertEye\SafeDriveVision

if exist "myenv_311" (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv myenv_311
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [2/5] Activating virtual environment...
call myenv_311\Scripts\activate.bat

REM Upgrade pip
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip

REM Install Python dependencies
echo [4/5] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo WARNING: Some packages failed to install
    echo Continuing anyway...
)

REM Install dlib
echo.
echo [5/5] Installing dlib (facial landmarks)...
echo Attempting to install dlib from PyPI...
pip install dlib
if errorlevel 1 (
    echo.
    echo WARNING: dlib installation failed
    echo You can install it manually later using setup_dlib.bat
    echo The app will still run but facial detection will be disabled
    echo.
)

REM Install Flutter dependencies
echo.
echo Installing Flutter dependencies...
cd /d F:\AlertEye\flutter_app
flutter pub get

echo.
echo ========================================
echo  Installation Complete!
echo ========================================
echo.
echo Note: If dlib failed to install, run setup_dlib.bat
echo.
echo To start the application:
echo   - Double-click: start_app.bat
echo   OR
echo   - Run manually:
echo     Terminal 1: cd SafeDriveVision ^&^& myenv_311\Scripts\activate ^&^& python app.py
echo     Terminal 2: cd flutter_app ^&^& flutter run -d windows
echo.
pause