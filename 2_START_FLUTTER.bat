@echo off
echo ========================================
echo AlertEye Flutter App (Profile Mode)
echo ========================================
echo.
echo IMPORTANT: Make sure backend is running first!
echo Backend should be at: http://localhost:8000
echo.
echo Starting Flutter app in PROFILE mode for best performance...
echo.

cd flutter_app
flutter run -d windows --profile

pause
