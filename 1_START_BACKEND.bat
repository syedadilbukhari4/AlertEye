@echo off
echo ========================================
echo AlertEye Backend
echo ========================================
echo.
echo Starting backend server...
echo Backend will run at: http://localhost:8000
echo.

cd backend
call ..\myenv_311\Scripts\activate.bat
python app.py

pause
