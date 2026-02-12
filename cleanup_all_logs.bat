@echo off
REM ========================================================
REM Daily Log Cleanup Job - All Trading Analytics Projects
REM ========================================================
REM Deletes log files older than 5 days across all projects.
REM Keeps the most recent 5 days of logs for troubleshooting.
REM
REM Projects covered:
REM   1. streamlit-trading-dashboard (Strategy 2 + Signal Tracking)
REM   2. sqlserver_copilot           (NASDAQ ML - Strategy 1)
REM   3. sqlserver_copilot_nse       (NSE ML - Strategy 1)
REM   4. sqlserver_copilot_forex     (Forex ML - Strategy 1)
REM   5. stockdata_agenticai         (Agentic AI)
REM
REM Schedule: Daily via Windows Task Scheduler
REM Recommended time: 11:00 PM (after all jobs complete)
REM ========================================================

echo.
echo ============================================
echo   Daily Log Cleanup - All Projects
echo   Started: %date% %time%
echo ============================================
echo.

REM Retention period in days (keep last 5 days)
set RETENTION_DAYS=5

REM Base path (all projects are on Desktop)
set BASE=%USERPROFILE%\OneDrive\Desktop

REM Track totals
set TOTAL_DELETED=0
set TOTAL_ERRORS=0

REM ----------------------------------------
REM 1. streamlit-trading-dashboard\logs
REM ----------------------------------------
echo [1/5] Cleaning streamlit-trading-dashboard\logs ...
set LOG_DIR=%BASE%\streamlit-trading-dashboard\logs
if exist "%LOG_DIR%" (
    forfiles /p "%LOG_DIR%" /s /m *.log /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo       Cleaned successfully.
    ) else (
        echo       No files older than %RETENTION_DAYS% days found, or folder empty.
    )
) else (
    echo       Folder not found, skipping.
)
echo.

REM Also clean the root-level summary logs if they get too large (> 1 MB)
for %%F in ("%BASE%\streamlit-trading-dashboard\prediction_job.log" "%BASE%\streamlit-trading-dashboard\signal_tracking.log") do (
    if exist "%%~F" (
        for %%A in ("%%~F") do (
            if %%~zA GTR 1048576 (
                echo   Trimming %%~nxF (over 1 MB^)...
                REM Keep last 100 lines
                powershell -Command "Get-Content '%%~F' -Tail 100 | Set-Content '%%~F.tmp'; Move-Item -Force '%%~F.tmp' '%%~F'"
            )
        )
    )
)

REM ----------------------------------------
REM 2. sqlserver_copilot\logs (NASDAQ ML)
REM ----------------------------------------
echo [2/5] Cleaning sqlserver_copilot\logs ...
set LOG_DIR=%BASE%\sqlserver_copilot\logs
if exist "%LOG_DIR%" (
    forfiles /p "%LOG_DIR%" /s /m *.log /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo       Cleaned successfully.
    ) else (
        echo       No files older than %RETENTION_DAYS% days found, or folder empty.
    )
    REM Also clean .txt logs
    forfiles /p "%LOG_DIR%" /s /m *.txt /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
) else (
    echo       Folder not found, skipping.
)
echo.

REM ----------------------------------------
REM 3. sqlserver_copilot_nse\logs (NSE ML)
REM ----------------------------------------
echo [3/5] Cleaning sqlserver_copilot_nse\logs ...
set LOG_DIR=%BASE%\sqlserver_copilot_nse\logs
if exist "%LOG_DIR%" (
    forfiles /p "%LOG_DIR%" /s /m *.log /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo       Cleaned successfully.
    ) else (
        echo       No files older than %RETENTION_DAYS% days found, or folder empty.
    )
    forfiles /p "%LOG_DIR%" /s /m *.txt /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
) else (
    echo       Folder not found, skipping.
)
echo.

REM ----------------------------------------
REM 4. sqlserver_copilot_forex\logs (Forex ML)
REM ----------------------------------------
echo [4/5] Cleaning sqlserver_copilot_forex\logs ...
set LOG_DIR=%BASE%\sqlserver_copilot_forex\logs
if exist "%LOG_DIR%" (
    forfiles /p "%LOG_DIR%" /s /m *.log /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo       Cleaned successfully.
    ) else (
        echo       No files older than %RETENTION_DAYS% days found, or folder empty.
    )
    forfiles /p "%LOG_DIR%" /s /m *.txt /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
) else (
    echo       Folder not found, skipping.
)
echo.

REM ----------------------------------------
REM 5. stockdata_agenticai\logs (Agentic AI)
REM ----------------------------------------
echo [5/5] Cleaning stockdata_agenticai\logs ...
set LOG_DIR=%BASE%\stockdata_agenticai\logs
if exist "%LOG_DIR%" (
    forfiles /p "%LOG_DIR%" /s /m *.log /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo       Cleaned successfully.
    ) else (
        echo       No files older than %RETENTION_DAYS% days found, or folder empty.
    )
    forfiles /p "%LOG_DIR%" /s /m *.txt /d -%RETENTION_DAYS% /c "cmd /c echo   Deleting @path && del @path" 2>nul
) else (
    echo       Folder not found, skipping.
)
echo.

REM ----------------------------------------
REM Summary
REM ----------------------------------------
echo ============================================
echo   Log Cleanup Completed
echo   Retention: Last %RETENTION_DAYS% days kept
echo   Finished: %date% %time%
echo ============================================
echo.

REM Log this run to a central cleanup history file
echo [%date% %time%] Log cleanup completed (retention: %RETENTION_DAYS% days) >> "%BASE%\streamlit-trading-dashboard\cleanup_history.log"

exit /b 0
