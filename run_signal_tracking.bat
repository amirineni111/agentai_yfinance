@echo off
REM ========================================================
REM Daily Double/Triple Strategy Signal Tracking Job
REM ========================================================
REM Run this batch file daily via Windows Task Scheduler
REM Recommended time: 7:00 PM (after market close and data updates)
REM ========================================================

echo.
echo ============================================
echo   Double/Triple Strategy Signal Tracking
echo   Started: %date% %time%
echo ============================================
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

REM Set log file with timestamp
set LOGFILE=logs\signal_tracking_%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.log
set LOGFILE=%LOGFILE: =0%

REM Run the signal tracking job with output to log file
echo Running signal tracking job...
echo Output will be saved to: %LOGFILE%
python daily_signal_tracking_job.py > "%LOGFILE%" 2>&1

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================
    echo   Signal Tracking Completed Successfully!
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    
    REM Log success
    echo [%date% %time%] SUCCESS: Daily signal tracking job completed >> signal_tracking.log
    echo.
    echo Log file saved: %LOGFILE%
    echo Check signal_tracking.log for history
) else (
    echo.
    echo ============================================
    echo   ERROR: Signal Tracking Job Failed!
    echo   Error Code: %ERRORLEVEL%
    echo   Finished: %date% %time%
    echo ============================================
    echo.
    
    REM Log error
    echo [%date% %time%] ERROR: Daily signal tracking job failed with code %ERRORLEVEL% >> signal_tracking.log
    echo.
    echo Error details in: %LOGFILE%
    echo Check signal_tracking.log for history
)

REM Auto-close when done (for scheduled tasks)
exit /b %ERRORLEVEL%
