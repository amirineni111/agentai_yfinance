# ========================================================
# Setup Windows Scheduled Task for Signal Tracking
# ========================================================
# Run this script to create a scheduled task that runs daily
# at 7:00 PM to track Double/Triple strategy signals
# ========================================================

$taskName = "DailySignalTracking"
$scriptPath = "$PSScriptRoot\run_signal_tracking.bat"
$description = "Daily Double/Triple Strategy Signal Tracking - Captures crossover signals and validates accuracy after 7, 14, and 30 days"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Signal Tracking Scheduled Task Setup" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "Task '$taskName' already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to recreate it? (Y/N)"
    if ($response -ne 'Y' -and $response -ne 'y') {
        Write-Host "Setup cancelled." -ForegroundColor Yellow
        exit
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Existing task removed.`n" -ForegroundColor Green
}

# Create the action (run the batch file)
$action = New-ScheduledTaskAction -Execute $scriptPath

# Create the trigger (daily at 7:00 PM)
$trigger = New-ScheduledTaskTrigger -Daily -At "19:00"

# Create settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register the task
Register-ScheduledTask `
    -TaskName $taskName `
    -Description $description `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Scheduled Task Created Successfully!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Green

Write-Host "Task Details:" -ForegroundColor Cyan
Write-Host "  Name: $taskName" -ForegroundColor White
Write-Host "  Schedule: Daily at 7:00 PM" -ForegroundColor White
Write-Host "  Script: $scriptPath" -ForegroundColor White

Write-Host "`nTo manage this task:" -ForegroundColor Cyan
Write-Host "  View: Get-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Run now: Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Disable: Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray
Write-Host "  Remove: Unregister-ScheduledTask -TaskName '$taskName'" -ForegroundColor Gray

Write-Host "`n" -ForegroundColor Green
