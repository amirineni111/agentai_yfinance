# Flight Status Dashboard Launcher (PowerShell)
Write-Host "🛩️ Flight Status Dashboard Launcher" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Change to project directory
Set-Location "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
Write-Host "📍 Project directory: $(Get-Location)" -ForegroundColor Yellow

# Check if virtual environment exists and activate it
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "🐍 Activating virtual environment..." -ForegroundColor Green
    & .\venv\Scripts\Activate.ps1
} elseif (Test-Path "venv\Scripts\activate.bat") {
    Write-Host "🐍 Activating virtual environment..." -ForegroundColor Green
    & .\venv\Scripts\activate.bat
} else {
    Write-Host "⚠️  Virtual environment not found, using system Python" -ForegroundColor Yellow
}

# Test environment
Write-Host "`n🧪 Running environment tests..." -ForegroundColor Yellow
$testResult = python test_flight_status.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Environment tests failed! Please fix issues above." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "`n✅ Environment tests passed!" -ForegroundColor Green
Write-Host "`n🚀 Starting Flight Status Dashboard..." -ForegroundColor Cyan
Write-Host "📱 Dashboard will open at: http://localhost:8502" -ForegroundColor Yellow
Write-Host "💡 To stop the dashboard, press Ctrl+C in this window" -ForegroundColor Gray
Write-Host ""

try {
    # Start the dashboard
    streamlit run flight_status_dashboard.py --server.port 8502 --server.headless false
} catch {
    Write-Host "❌ Error starting dashboard: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
