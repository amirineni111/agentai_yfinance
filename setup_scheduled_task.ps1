# ========================================================
# Setup Windows Task Scheduler for Daily Predictions
# ========================================================
# This script creates a scheduled task to run predictions daily
# Run this script once to set up the automation
# ========================================================

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Setting up Daily Prediction Task" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Get the script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$batchFile = Join-Path $scriptPath "run_daily_predictions.bat"

# Check if batch file exists
if (-not (Test-Path $batchFile)) {
    Write-Host "ERROR: run_daily_predictions.bat not found!" -ForegroundColor Red
    Write-Host "Expected location: $batchFile" -ForegroundColor Yellow
    exit 1
}

# Task configuration
$taskName = "AI_Price_Prediction_Daily"
$taskDescription = "Daily AI Price Prediction Job - Generates predictions and updates accuracy metrics"
$taskTime = "18:00"  # 6:00 PM (after market close)

Write-Host "Task Configuration:" -ForegroundColor Yellow
Write-Host "  Name: $taskName" -ForegroundColor White
Write-Host "  Description: $taskDescription" -ForegroundColor White
Write-Host "  Schedule: Daily at $taskTime" -ForegroundColor White
Write-Host "  Script: $batchFile`n" -ForegroundColor White

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Scheduled task already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to update it? (Y/N)"
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "Removing existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    else {
        Write-Host "Setup cancelled." -ForegroundColor Yellow
        exit 0
    }
}

try {
    # Create the action (run the batch file)
    $action = New-ScheduledTaskAction -Execute $batchFile -WorkingDirectory $scriptPath
    
    # Create the trigger (daily at specified time)
    $trigger = New-ScheduledTaskTrigger -Daily -At $taskTime
    
    # Create the principal (run with highest privileges)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
    
    # Create the settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    
    # Register the task
    Register-ScheduledTask `
        -TaskName $taskName `
        -Description $taskDescription `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings | Out-Null
    
    Write-Host "`n============================================" -ForegroundColor Green
    Write-Host "  Task Created Successfully!" -ForegroundColor Green
    Write-Host "============================================`n" -ForegroundColor Green
    
    Write-Host "Next Steps:" -ForegroundColor Yellow
    Write-Host "  1. Open Task Scheduler (taskschd.msc)" -ForegroundColor White
    Write-Host "  2. Find task: $taskName" -ForegroundColor White
    Write-Host "  3. Right-click and select 'Run' to test it" -ForegroundColor White
    Write-Host "  4. Check prediction_job.log for results`n" -ForegroundColor White
    
    # Ask if user wants to run now
    $response = Read-Host "Do you want to run the task now for testing? (Y/N)"
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "`nStarting task..." -ForegroundColor Yellow
        Start-ScheduledTask -TaskName $taskName
        Write-Host "Task started! Check the log file for progress." -ForegroundColor Green
    }
}
catch {
    Write-Host "`nERROR: Failed to create scheduled task!" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "`nTry running this script as Administrator." -ForegroundColor Yellow
    exit 1
}

Write-Host "`nSetup complete!`n" -ForegroundColor Green
