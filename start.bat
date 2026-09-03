@echo off
setlocal enabledelayedexpansion

echo =====================================================
echo   AI-Powered Elderly Healthcare System
echo   Real-Time Adaptive Reminder Engine
echo =====================================================
echo.

REM Check if virtual environment exists
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo.
    echo SOLUTION: Run setup.bat first to set up the application
    echo.
    pause
    exit /b 1
)

echo Features:
echo   - WebSocket real-time updates
echo   - Web Push notifications (works when app is closed)
echo   - Automatic voice reminders (Telugu + English)
echo   - ML-based risk scoring
echo   - 3-level adaptive escalation
echo.

echo Checking virtual environment...
if not exist venv\Scripts\activate (
    echo ERROR: Virtual environment is corrupted!
    echo.
    echo SOLUTION: Delete the 'venv' folder and run setup.bat again
    echo.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment!
    echo.
    pause
    exit /b 1
)

echo.
echo Checking Python packages...
venv\Scripts\python.exe -c "import flask, flask_socketio" 2>nul
if errorlevel 1 (
    echo ERROR: Required packages not installed!
    echo.
    echo SOLUTION: Run setup.bat to install dependencies
    echo.
    pause
    exit /b 1
)

echo Starting server (WebSocket + REST API)...
echo.
echo Open your browser:
echo   Caretaker Dashboard : http://localhost:5000/dashboard
echo   Elder View          : http://localhost:5000/elder-view
echo   Analytics           : http://localhost:5000/analytics
echo.
echo Checking if port 5000 is available...
for /f "tokens=5" %%a in ('netstat -ano ^| find "5000"') do (
    echo WARNING: Port 5000 is already in use by another process (PID: %%a)
    echo.
    echo SOLUTION: 
    echo   - Close other applications using port 5000
    echo   - Or change PORT in .env file and restart
)
echo.
echo Press Ctrl+C to stop.
echo.

REM Run the application
venv\Scripts\python.exe run.py
if errorlevel 1 (
    echo.
    echo ERROR: Application failed to start!
    echo.
    echo TROUBLESHOOTING:
    echo   1. Make sure MySQL/SQLite database is accessible
    echo   2. Check that all packages are installed (run setup.bat)
    echo   3. Check .env file configuration
    echo   4. See QUICK_START.txt for more help
    echo.
    pause
)
