@echo off
REM Flight Status Dashboard Launcher
echo 🛩️ Flight Status Dashboard Launcher
echo ================================
cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"

echo 📍 Current directory: %CD%
echo.

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo 🐍 Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️  Virtual environment not found, using system Python
)

REM Test environment first
echo 🧪 Running environment tests...
python test_flight_status.py
if errorlevel 1 (
    echo.
    echo ❌ Environment tests failed! Please fix issues above.
    pause
    exit /b 1
)

echo.
echo ✅ Environment tests passed!
echo.
echo 🚀 Starting Flight Status Dashboard...
echo 📱 Dashboard will open at: http://localhost:8502
echo.
echo 💡 To stop the dashboard, press Ctrl+C in this window
echo.

REM Start the dashboard
streamlit run flight_status_dashboard.py --server.port 8502 --server.headless false

pause
