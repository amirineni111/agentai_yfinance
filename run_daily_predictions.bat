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

REM Run the prediction job
echo Running prediction job...
python daily_prediction_job.py

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
)

REM Keep window open for manual runs (comment out for scheduled runs)
REM pause

exit /b %ERRORLEVEL%
