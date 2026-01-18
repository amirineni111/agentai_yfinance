@echo off
REM ========================================================
REM Quick Setup Script for AI Prediction Backtesting
REM ========================================================

echo.
echo ============================================
echo   AI Prediction Backtesting Setup
echo ============================================
echo.
echo This will set up the backtesting system:
echo   1. Create database table
echo   2. Run initial prediction job
echo   3. Setup daily automation
echo.
pause

REM Step 1: Create database table
echo.
echo [Step 1/3] Creating database table...
echo.
sqlcmd -S localhost\MSSQLSERVER01 -d stockdata_db -i create_prediction_history_table.sql

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to create database table!
    echo Make sure SQL Server is running and connection details are correct.
    pause
    exit /b 1
)

echo.
echo SUCCESS: Database table created!
echo.

REM Step 2: Run initial prediction job
echo.
echo [Step 2/3] Running initial prediction job...
echo This may take 10-15 minutes for first run...
echo.
python daily_prediction_job.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Prediction job had errors. Check the output above.
    echo You can continue and fix issues later.
    echo.
) else (
    echo.
    echo SUCCESS: Initial predictions generated!
    echo.
)

REM Step 3: Setup automation
echo.
echo [Step 3/3] Setting up daily automation...
echo.
echo Please run the following command in PowerShell as Administrator:
echo.
echo   powershell -ExecutionPolicy Bypass -File setup_scheduled_task.ps1
echo.
echo This will create a scheduled task to run predictions daily at 6 PM.
echo.

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Next Steps:
echo   1. Run the PowerShell command above to setup automation
echo   2. Start your Streamlit dashboard
echo   3. Go to AI Price Predictions page
echo   4. Enable "Show Prediction Accuracy Analysis"
echo.
echo See BACKTESTING_SETUP_GUIDE.md for detailed instructions.
echo.
pause
