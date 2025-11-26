@echo off
REM Test the Fixed Flight Status Dashboard
echo 🛩️ Testing Fixed Flight Status Dashboard
echo ======================================
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

echo.
echo ✅ Starting Fixed Flight Status Dashboard...
echo 📱 Dashboard will open at: http://localhost:8503
echo.
echo 💡 To stop the dashboard, press Ctrl+C in this window
echo.

REM Start the fixed dashboard
streamlit run flight_status_dashboard_fixed.py --server.port 8503 --server.headless false

pause
