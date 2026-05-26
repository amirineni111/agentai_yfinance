@echo off
echo Starting Trading Dashboard...
cd /d "c:\Users\sreea\OneDrive\Desktop\streamlit-trading-dashboard"
echo Current directory: %CD%

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv. Ensure venv exists at venv\Scripts\activate.bat
    pause
    exit /b 1
)
echo Virtual environment activated.

echo.
echo Dashboard will be available at: http://localhost:8501
echo Press Ctrl+C to stop the dashboard
echo.

streamlit run streamlitapp_20251123_v2.py --server.port=8501
if errorlevel 1 (
    echo.
    echo Error starting dashboard. Trying fallback...
    python -m streamlit run streamlitapp_20251123_v2.py --server.port=8501
)

echo.
echo ✅ Dashboard stopped.
pause
