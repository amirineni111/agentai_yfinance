@echo off
REM ========================================================
REM Daily AI Price Prediction Job - Windows Task Scheduler
REM ========================================================
REM Run this batch file daily via Windows Task Scheduler
REM Recommended time: 6:00 PM (after market close)
REM ========================================================

echo.
echo ============================================
echo   Daily AI Price Prediction Job
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Activate Python environment if needed (uncomment if using venv)
REM call venv\Scripts\activate.bat

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Fixed log file — overwritten on each run
set LOGFILE=logs\prediction_latest.log

REM Run the prediction job with output to log file
echo Running prediction job...
echo Output will be saved to: %LOGFILE%
python daily_prediction_job.py > "%LOGFILE%" 2>&1

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   Prediction Job Completed Successfully!
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    
    REM Log success
    echo [%date% %time%] SUCCESS: Daily prediction job completed >> prediction_job.log
    echo.
    echo Log file saved: %LOGFILE%
    echo Check prediction_job.log for history
) else (
    echo.
    echo ============================================
    echo   ERROR: Prediction Job Failed!
    echo   Error Code: %ERRORLEVEL%
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    
    REM Log error
    echo [%date% %time%] ERROR: Daily prediction job failed with code %ERRORLEVEL% >> prediction_job.log
    echo.
    echo Error details in: %LOGFILE%
    echo Check prediction_job.log for history
)

REM Comment out pause to auto-close window when scheduled
REM echo.
REM echo Press any key to close this window...
REM pause > nul

exit /b %ERRORLEVEL%
