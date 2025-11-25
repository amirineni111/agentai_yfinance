@echo off
echo 🚀 Starting Trading Dashboard...
cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
echo 📍 Current directory: %CD%

echo.
echo 🔍 Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found! Please install Python first.
    echo 📥 Download from: https://python.org/downloads
    pause
    exit /b 1
)

echo ✅ Python found!
echo.
echo 📦 Installing required packages...
echo Installing streamlit...
pip install streamlit --quiet --disable-pip-version-check
echo Installing pyodbc...
pip install pyodbc --quiet --disable-pip-version-check
echo Installing pandas...
pip install pandas --quiet --disable-pip-version-check
echo Installing plotly...
pip install plotly --quiet --disable-pip-version-check
echo Installing numpy...
pip install numpy --quiet --disable-pip-version-check

echo.
echo ✅ All packages installed!
echo 🌐 Dashboard will be available at: http://localhost:8502
echo 📖 Press Ctrl+C to stop the dashboard
echo.

streamlit run streamlitapp_20251123_v2.py
if errorlevel 1 (
    echo.
    echo ❌ Error starting dashboard. Trying alternative method...
    python -m streamlit run streamlitapp_20251123_v2.py
)

echo.
echo ✅ Dashboard stopped.
pause
