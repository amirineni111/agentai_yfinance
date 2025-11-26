# PowerShell Deployment Preparation Script for multizoneus.com
# Run this on your Windows machine to prepare for deployment

param(
    [string]$DeploymentMethod = "docker",
    [string]$Domain = "multizoneus.com",
    [string]$GitRepo = ""
)

Write-Host "🚀 Preparing AI Trading Dashboard for deployment to $Domain" -ForegroundColor Green

# Check prerequisites
Write-Host "`n📋 Checking prerequisites..." -ForegroundColor Yellow

# Check if Git is installed
try {
    git --version | Out-Null
    Write-Host "✅ Git is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Git is not installed. Please install Git first." -ForegroundColor Red
    exit 1
}

# Check Python
try {
    python --version | Out-Null
    Write-Host "✅ Python is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed. Please install Python first." -ForegroundColor Red
    exit 1
}

# Create deployment directory
$deployDir = "trading-dashboard-deploy"
if (Test-Path $deployDir) {
    Write-Host "📁 Deployment directory already exists, backing up..." -ForegroundColor Yellow
    $backupDir = "${deployDir}_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Move-Item $deployDir $backupDir
}

New-Item -ItemType Directory -Name $deployDir | Out-Null
Set-Location $deployDir

Write-Host "`n📂 Created deployment directory: $deployDir" -ForegroundColor Green

# Copy application files
Write-Host "`n📋 Copying application files..." -ForegroundColor Yellow

$sourceDir = "..\agentai_yfinance"
if (Test-Path $sourceDir) {
    # Copy main files
    $filesToCopy = @(
        "streamlitapp_20251123_v2.py",
        "streamlit_cloud_version.py", 
        "flask_app.py",
        "requirements_production.txt",
        "Dockerfile",
        "docker-compose.yml",
        "deploy.sh",
        ".env"
    )
    
    foreach ($file in $filesToCopy) {
        $sourcePath = Join-Path $sourceDir $file
        if (Test-Path $sourcePath) {
            Copy-Item $sourcePath . -Force
            Write-Host "✅ Copied $file" -ForegroundColor Green
        } else {
            Write-Host "⚠️  $file not found, skipping..." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "❌ Source directory not found: $sourceDir" -ForegroundColor Red
    exit 1
}

# Create environment file
Write-Host "`n🔧 Creating environment configuration..." -ForegroundColor Yellow

$envContent = @"
# Production environment variables for $Domain
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Domain configuration
DOMAIN=$Domain
EMAIL=admin@$Domain

# API Keys (replace with your actual keys)
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here
FINNHUB_API_KEY=your_finnhub_key_here
POLYGON_API_KEY=your_polygon_key_here

# Security
SECRET_KEY=$(New-Guid)
ALLOWED_HOSTS=$Domain,www.$Domain,localhost

# Database (if needed)
DATABASE_URL=sqlite:///trading_dashboard.db
REDIS_URL=redis://localhost:6379/0
"@

$envContent | Out-File -FilePath ".env" -Encoding utf8
Write-Host "✅ Created .env file" -ForegroundColor Green

# Update docker-compose.yml with correct domain
if (Test-Path "docker-compose.yml") {
    Write-Host "`n🐳 Updating Docker configuration for $Domain..." -ForegroundColor Yellow
    
    $dockerContent = Get-Content "docker-compose.yml" -Raw
    $dockerContent = $dockerContent -replace "multizoneus\.com", $Domain
    $dockerContent = $dockerContent -replace "your-email@example\.com", "admin@$Domain"
    
    $dockerContent | Out-File -FilePath "docker-compose.yml" -Encoding utf8
    Write-Host "✅ Updated docker-compose.yml" -ForegroundColor Green
}

# Create README for deployment
$readmeContent = @"
# AI Trading Dashboard Deployment

## Quick Start

### Option 1: Streamlit Cloud
1. Push this folder to GitHub
2. Deploy on share.streamlit.io using streamlit_cloud_version.py
3. Configure domain redirect from $Domain

### Option 2: Docker VPS
1. Copy this folder to your server
2. Run: chmod +x deploy.sh && ./deploy.sh
3. Configure DNS A record pointing $Domain to your server IP

### Option 3: Local Testing
``````bash
pip install -r requirements_production.txt
streamlit run streamlit_cloud_version.py --server.port 8501
``````

## Files Included
- streamlitapp_20251123_v2.py (Full version with SQL Server)
- streamlit_cloud_version.py (Cloud-ready version with yfinance)
- flask_app.py (Flask alternative)
- Dockerfile & docker-compose.yml (Docker deployment)
- requirements_production.txt (All dependencies)
- .env (Environment configuration)

## Next Steps
1. Update API keys in .env file
2. Test locally first
3. Choose deployment method
4. Configure domain DNS
5. Deploy to production

Generated on: $(Get-Date)
Domain: $Domain
"@

$readmeContent | Out-File -FilePath "README.md" -Encoding utf8

# Create GitHub workflow (optional)
$workflowDir = ".github\workflows"
New-Item -ItemType Directory -Path $workflowDir -Force | Out-Null

$workflowContent = @"
name: Deploy to Production

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements_production.txt
    - name: Test application
      run: |
        python -c "import streamlit; print('Streamlit OK')"

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - name: Deploy to server
      run: |
        echo "Add your deployment script here"
        # Example: SSH to server and pull latest code
"@

$workflowContent | Out-File -FilePath "$workflowDir\deploy.yml" -Encoding utf8

# Initialize git repository
Write-Host "`n📦 Initializing Git repository..." -ForegroundColor Yellow

git init 2>$null
git add . 2>$null
git commit -m "Initial deployment setup for $Domain" 2>$null

Write-Host "✅ Git repository initialized" -ForegroundColor Green

# Test application locally
Write-Host "`n🧪 Testing application locally..." -ForegroundColor Yellow

try {
    python -c "import streamlit, pandas, plotly, numpy; print('All imports successful')"
    Write-Host "✅ All Python dependencies are available" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Some Python packages may be missing. Install with:" -ForegroundColor Yellow
    Write-Host "pip install -r requirements_production.txt" -ForegroundColor Cyan
}

# Summary
Write-Host "`n🎉 Deployment preparation completed!" -ForegroundColor Green
Write-Host "`n📋 Summary:" -ForegroundColor Yellow
Write-Host "📁 Deployment directory: $(Get-Location)" -ForegroundColor Cyan
Write-Host "🌐 Target domain: $Domain" -ForegroundColor Cyan
Write-Host "📄 Files prepared: $(Get-ChildItem -File | Measure-Object | Select-Object -ExpandProperty Count)" -ForegroundColor Cyan

Write-Host "`n🚀 Next Steps:" -ForegroundColor Yellow
Write-Host "1. Review and update .env file with your API keys" -ForegroundColor White
Write-Host "2. Test locally: streamlit run streamlit_cloud_version.py" -ForegroundColor White
Write-Host "3. Push to GitHub: git remote add origin YOUR_REPO_URL && git push -u origin main" -ForegroundColor White
Write-Host "4. Choose deployment method from DEPLOYMENT_GUIDE_COMPLETE.md" -ForegroundColor White
Write-Host "5. Configure DNS for $Domain" -ForegroundColor White

Write-Host "`n📖 Deployment Options:" -ForegroundColor Yellow
Write-Host "• Streamlit Cloud (Free, Easy): https://share.streamlit.io/" -ForegroundColor White
Write-Host "• Docker VPS (Recommended): Use docker-compose.yml" -ForegroundColor White  
Write-Host "• Traditional Hosting: Use flask_app.py" -ForegroundColor White

Write-Host "`n✅ Ready for deployment to $Domain!" -ForegroundColor Green
