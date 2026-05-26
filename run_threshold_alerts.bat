@echo off
REM ========================================================
REM Daily Price Threshold Alert Job
REM ========================================================
REM Run this batch file via Windows Task Scheduler.
REM It scans NSE_500 and NASDAQ_top100 for active monitored
REM stocks whose latest close price has breached upper_threshold
REM or lower_threshold, and sends one HTML email summary.
REM ========================================================

echo.
echo ============================================
echo   Price Threshold Alert Job
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Fixed log file — overwritten on each run
set LOGFILE=logs\threshold_alert_latest.log

REM Run the alert job using the venv Python, capturing output to log file
echo Running threshold alert scan...
"%~dp0venv\Scripts\python.exe" threshold_alert_job.py > "%LOGFILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] SUCCESS: Threshold alert job completed >> threshold_alerts.log
    echo Job completed successfully. Check log: %LOGFILE%
) else (
    echo [%date% %time%] ERROR: Threshold alert job failed with code %ERRORLEVEL% >> threshold_alerts.log
    echo Job failed with exit code %ERRORLEVEL%. Check log: %LOGFILE%
)

exit /b %ERRORLEVEL%
