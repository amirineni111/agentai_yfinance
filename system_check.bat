@echo off
title Trading Dashboard - System Check
color 0B

echo.
echo ===============================================
echo   🔧 TRADING DASHBOARD SYSTEM CHECK
echo ===============================================
echo.

cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"

echo 📍 Current Directory: %CD%
echo.

echo 🔍 Checking System Requirements...
echo.

REM Check Python
echo [1/6] Python Installation:
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ FAILED: Python not found
    echo    Solution: Install Python from https://python.org/downloads
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo ✅ SUCCESS: Python %PYTHON_VERSION%
)
echo.

REM Check pip
echo [2/6] pip (Package Installer):
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ FAILED: pip not found
) else (
    echo ✅ SUCCESS: pip available
)
echo.

REM Check main application file
echo [3/6] Application File:
if exist "streamlitapp_20251123_v2.py" (
    echo ✅ SUCCESS: streamlitapp_20251123_v2.py found
) else (
    echo ❌ FAILED: streamlitapp_20251123_v2.py not found
)
echo.

REM Check SQL Server connection (optional)
echo [4/6] SQL Server Connection:
sqlcmd -S localhost\MSSQLSERVER01 -E -Q "SELECT 1" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  WARNING: Cannot connect to SQL Server
    echo    This may cause data loading issues
) else (
    echo ✅ SUCCESS: SQL Server accessible
)
echo.

REM Check required Python packages
echo [5/6] Required Python Packages:
set PACKAGES=streamlit pyodbc pandas plotly numpy
for %%p in (%PACKAGES%) do (
    python -c "import %%p" >nul 2>&1
    if errorlevel 1 (
        echo ❌ MISSING: %%p
    ) else (
        echo ✅ FOUND: %%p
    )
)
echo.

REM Check network connectivity
echo [6/6] Network Ports:
netstat -an | findstr ":8502" >nul 2>&1
if not errorlevel 1 (
    echo ⚠️  WARNING: Port 8502 is in use
    echo    Dashboard might start on a different port
) else (
    echo ✅ SUCCESS: Port 8502 available
)
echo.

echo ===============================================
echo   📋 RECOMMENDED ACTIONS:
echo.
echo   1. If Python is missing: Install from python.org
echo   2. If packages are missing: Run 'setup_and_start.bat'
echo   3. If SQL Server fails: Check if service is running
echo   4. If port is busy: Dashboard will use next available port
echo.
echo ===============================================

pause
