@echo off
REM ========================================================
REM Daily AI Price Prediction Job - NSE 500 ONLY
REM ========================================================
REM Run this batch file daily via Windows Task Scheduler
REM Recommended time: 5:30 PM IST (after NSE market close)
REM ========================================================

echo.
echo ============================================
echo   Daily AI Prediction Job - NSE 500
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Fixed log file — overwritten on each run
set LOGFILE=logs\prediction_NSE_latest.log

REM Run the prediction job for NSE 500 only
echo Running NSE 500 prediction job...
echo Output will be saved to: %LOGFILE%
"%~dp0venv\Scripts\python.exe" daily_prediction_job.py --market "NSE 500" > "%LOGFILE%" 2>&1

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   NSE 500 Prediction Job Completed!
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] SUCCESS: NSE 500 prediction job completed >> prediction_job.log
    echo Log file saved: %LOGFILE%
) else (
    echo.
    echo ============================================
    echo   ERROR: NSE 500 Prediction Job Failed!
    echo   Error Code: %ERRORLEVEL%
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] ERROR: NSE 500 prediction job failed with code %ERRORLEVEL% >> prediction_job.log
    echo Error details in: %LOGFILE%
)

exit /b %ERRORLEVEL%
