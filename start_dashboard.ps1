# Trading Dashboard Startup Script
Write-Host "🚀 Starting Trading Dashboard..." -ForegroundColor Green

# Navigate to app directory
Set-Location "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"

# Check Python version
Write-Host "🐍 Python Version:" -ForegroundColor Yellow
python --version

# Check if SQL Server is accessible
Write-Host "📊 Checking SQL Server connection..." -ForegroundColor Yellow
try {
    sqlcmd -S localhost\MSSQLSERVER01 -E -Q "SELECT @@VERSION" -h -1 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SQL Server connection successful!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ SQL Server connection issues detected" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ Could not test SQL Server connection" -ForegroundColor Yellow
}

# Check if required packages are installed
Write-Host "📦 Checking dependencies..." -ForegroundColor Yellow
$packages = @("streamlit", "pyodbc", "pandas", "plotly", "numpy")
foreach ($package in $packages) {
    try {
        python -c "import $package" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $package installed" -ForegroundColor Green
        } else {
            Write-Host "❌ $package missing - installing..." -ForegroundColor Red
            pip install $package
        }
    } catch {
        Write-Host "❌ $package missing - installing..." -ForegroundColor Red
        pip install $package
    }
}

# Start Streamlit app
Write-Host "🌐 Starting Streamlit server..." -ForegroundColor Cyan
Write-Host "Dashboard will be available at: http://localhost:8502" -ForegroundColor Magenta

streamlit run streamlitapp_20251123_v2.py --server.headless=false

Write-Host "✅ Dashboard stopped." -ForegroundColor Green
