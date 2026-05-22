@echo off
REM ========================================================
REM Daily AI Price Prediction Job - FOREX ONLY
REM ========================================================
REM Run this batch file daily via Windows Task Scheduler
REM Recommended time: 6:00 PM EST (forex trades 24h but
REM aligning with NASDAQ close for consistency)
REM ========================================================

echo.
echo ============================================
echo   Daily AI Prediction Job - Forex
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set log file with timestamp
set LOGFILE=logs\prediction_Forex_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

REM Run the prediction job for Forex only
echo Running Forex prediction job...
echo Output will be saved to: %LOGFILE%
"%~dp0venv\Scripts\python.exe" daily_prediction_job.py --market "Forex" > "%LOGFILE%" 2>&1

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   Forex Prediction Job Completed!
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] SUCCESS: Forex prediction job completed >> prediction_job.log
    echo Log file saved: %LOGFILE%
) else (
    echo.
    echo ============================================
    echo   ERROR: Forex Prediction Job Failed!
    echo   Error Code: %ERRORLEVEL%
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    echo [%date% %time%] ERROR: Forex prediction job failed with code %ERRORLEVEL% >> prediction_job.log
    echo Error details in: %LOGFILE%
)

exit /b %ERRORLEVEL%
