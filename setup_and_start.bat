@echo off
title Trading Dashboard - Setup and Launch
color 0A

echo.
echo ===============================================
echo   📊 TRADING DASHBOARD SETUP AND LAUNCHER
echo ===============================================
echo.

REM Change to the correct directory
cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
echo 📍 Working Directory: %CD%
echo.

REM Check if Python is installed
echo 🔍 Step 1: Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python is not installed or not in PATH!
    echo.
    echo 📥 Please install Python from: https://python.org/downloads
    echo ⚠️  Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% found!
echo.

REM Upgrade pip first
echo 🔧 Step 2: Upgrading pip...
python -m pip install --upgrade pip --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ⚠️  Warning: Could not upgrade pip, continuing...
) else (
    echo ✅ pip upgraded successfully!
)
echo.

REM Install required packages
echo 📦 Step 3: Installing required packages...
echo.

echo   Installing streamlit...
python -m pip install streamlit --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ❌ Failed to install streamlit
    pause
    exit /b 1
)
echo   ✅ streamlit installed

echo   Installing pyodbc...
python -m pip install pyodbc --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ❌ Failed to install pyodbc
    pause
    exit /b 1
)
echo   ✅ pyodbc installed

echo   Installing pandas...
python -m pip install pandas --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ❌ Failed to install pandas
    pause
    exit /b 1
)
echo   ✅ pandas installed

echo   Installing plotly...
python -m pip install plotly --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ❌ Failed to install plotly
    pause
    exit /b 1
)
echo   ✅ plotly installed

echo   Installing numpy...
python -m pip install numpy --quiet --disable-pip-version-check
if errorlevel 1 (
    echo ❌ Failed to install numpy
    pause
    exit /b 1
)
echo   ✅ numpy installed

echo.
echo ✅ All packages installed successfully!
echo.

REM Check if the main Python file exists
if not exist "streamlitapp_20251123_v2.py" (
    echo ❌ ERROR: streamlitapp_20251123_v2.py not found!
    echo 📁 Expected location: %CD%\streamlitapp_20251123_v2.py
    echo.
    pause
    exit /b 1
)

echo 📊 Step 4: Starting Trading Dashboard...
echo.
echo ===============================================
echo   🌐 ACCESS YOUR DASHBOARD AT:
echo   http://localhost:8502
echo.
echo   📋 CONTROLS:
echo   • Press Ctrl+C in this window to stop
echo   • Close your browser to continue using
echo   • Don't close this window while using dashboard
echo ===============================================
echo.

REM Start the dashboard
python -m streamlit run streamlitapp_20251123_v2.py --server.headless=false
if errorlevel 1 (
    echo.
    echo ❌ Failed to start with python -m streamlit
    echo 🔄 Trying alternative method...
    streamlit run streamlitapp_20251123_v2.py
)

echo.
echo ✅ Dashboard stopped successfully.
echo 👋 Thank you for using Trading Dashboard!
pause
