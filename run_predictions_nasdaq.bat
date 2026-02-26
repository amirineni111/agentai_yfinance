@echo off
REM ========================================================
REM Daily AI Price Prediction Job - NASDAQ 100 ONLY
REM ========================================================
REM Run this batch file daily via Windows Task Scheduler
REM Recommended time: 6:00 PM EST (after NASDAQ market close)
REM ========================================================

echo.
echo ============================================
echo   Daily AI Prediction Job - NASDAQ 100
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set log file with timestamp
set LOGFILE=logs\prediction_NASDAQ_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

REM Run the prediction job for NASDAQ 100 only
echo Running NASDAQ 100 prediction job...
echo Output will be saved to: %LOGFILE%
python daily_prediction_job.py --market "NASDAQ 100" > "%LOGFILE%" 2>&1

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   NASDAQ 100 Prediction Job Completed!
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] SUCCESS: NASDAQ 100 prediction job completed >> prediction_job.log
    echo Log file saved: %LOGFILE%
) else (
    echo.
    echo ============================================
    echo   ERROR: NASDAQ 100 Prediction Job Failed!
    echo   Error Code: %ERRORLEVEL%
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] ERROR: NASDAQ 100 prediction job failed with code %ERRORLEVEL% >> prediction_job.log
    echo Error details in: %LOGFILE%
)

exit /b %ERRORLEVEL%
