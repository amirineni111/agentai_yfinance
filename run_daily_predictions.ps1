# ========================================================
# Daily AI Price Prediction Job - PowerShell Version
# ========================================================
# Run this script daily via Windows Task Scheduler
# Recommended time: 6:00 PM (after market close)
# ========================================================

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  Daily AI Price Prediction Job" -ForegroundColor Cyan
Write-Host "  Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "============================================`n" -ForegroundColor Cyan

# Change to script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Activate Python environment if needed (uncomment if using venv)
# & .\venv\Scripts\Activate.ps1

# Run the prediction job
Write-Host "Running prediction job..." -ForegroundColor Yellow

try {
    # Run Python script
    python daily_prediction_job.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n============================================" -ForegroundColor Green
        Write-Host "  Prediction Job Completed Successfully!" -ForegroundColor Green
        Write-Host "  Finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Green
        Write-Host "============================================`n" -ForegroundColor Green
        
        # Log success
        $logMessage = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SUCCESS: Daily prediction job completed"
        Add-Content -Path "prediction_job.log" -Value $logMessage
    }
    else {
        Write-Host "`n============================================" -ForegroundColor Red
        Write-Host "  ERROR: Prediction Job Failed!" -ForegroundColor Red
        Write-Host "  Error Code: $LASTEXITCODE" -ForegroundColor Red
        Write-Host "  Finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Red
        Write-Host "============================================`n" -ForegroundColor Red
        
        # Log error
        $logMessage = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: Daily prediction job failed with code $LASTEXITCODE"
        Add-Content -Path "prediction_job.log" -Value $logMessage
        
        exit $LASTEXITCODE
    }
}
catch {
    Write-Host "`n============================================" -ForegroundColor Red
    Write-Host "  CRITICAL ERROR!" -ForegroundColor Red
    Write-Host "  $_" -ForegroundColor Red
    Write-Host "============================================`n" -ForegroundColor Red
    
    # Log exception
    $logMessage = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] EXCEPTION: $_"
    Add-Content -Path "prediction_job.log" -Value $logMessage
    
    exit 1
}
