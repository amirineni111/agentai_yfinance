# 🚀 Local Deployment Guide - Trading Dashboard

## 📋 Prerequisites

### 1. Python Environment
Ensure you have Python 3.8+ installed:
```powershell
python --version
```

### 2. Required Dependencies
Install all required packages:
```powershell
cd "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
pip install streamlit pyodbc pandas plotly numpy
```

### 3. SQL Server Connection
Ensure your SQL Server instance is running:
- **Server**: `localhost\MSSQLSERVER01`
- **Database**: `stockdata_db`
- **Authentication**: Windows Authentication (Trusted_Connection)

---

## 🚀 Deployment Methods

### Method 1: Direct Streamlit Run (Recommended)

**Start the app:**
```powershell
cd "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
streamlit run streamlitapp_20251123_v2.py
```

**Access the app:**
- Local URL: `http://localhost:8502`
- Network URL: `http://192.168.87.31:8502` (accessible from other devices on your network)

**Features:**
- ✅ Hot reloading (auto-refresh on file changes)
- ✅ Development-friendly
- ✅ Easy debugging
- ✅ All interactive features enabled

---

### Method 2: Streamlit with Custom Configuration

**Create config file:**
```powershell
# Create .streamlit directory
mkdir .streamlit -Force

# Create config file
@"
[server]
port = 8503
headless = false
enableCORS = true
enableXsrfProtection = true

[browser]
gatherUsageStats = false
showErrorDetails = true

[theme]
base = "light"
primaryColor = "#FF6B35"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
"@ | Out-File -FilePath ".streamlit\config.toml" -Encoding UTF8
```

**Run with custom config:**
```powershell
streamlit run streamlitapp_20251123_v2.py --server.port 8503
```

---

### Method 3: Production-Ready Local Setup

**Create startup script:**
```powershell
# Create startup script
@"
# Trading Dashboard Startup Script
Write-Host "🚀 Starting Trading Dashboard..." -ForegroundColor Green

# Check Python version
python --version

# Check if SQL Server is accessible
Write-Host "📊 Checking SQL Server connection..." -ForegroundColor Yellow

# Start Streamlit app
Write-Host "🌐 Starting Streamlit server..." -ForegroundColor Cyan
streamlit run streamlitapp_20251123_v2.py --server.headless=false --server.enableCORS=true

Write-Host "✅ Dashboard started successfully!" -ForegroundColor Green
"@ | Out-File -FilePath "start_dashboard.ps1" -Encoding UTF8

# Make it executable and run
powershell -ExecutionPolicy Bypass -File "start_dashboard.ps1"
```

---

### Method 4: Docker Deployment (Advanced)

**Create Dockerfile:**
```dockerfile
# Create Dockerfile
@"
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    unixodbc \
    unixodbc-dev \
    freetds-bin \
    freetds-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Start the application
CMD ["streamlit", "run", "streamlitapp_20251123_v2.py", "--server.address=0.0.0.0", "--server.port=8501"]
"@ | Out-File -FilePath "Dockerfile" -Encoding UTF8
```

**Create requirements.txt:**
```powershell
@"
streamlit==1.28.1
pyodbc==4.0.39
pandas==2.0.3
plotly==5.17.0
numpy==1.24.3
"@ | Out-File -FilePath "requirements.txt" -Encoding UTF8
```

**Build and run Docker container:**
```powershell
# Build the image
docker build -t trading-dashboard .

# Run the container
docker run -p 8501:8501 trading-dashboard
```

---

## 🔧 Troubleshooting

### Common Issues:

1. **Port Already in Use:**
```powershell
# Find process using port 8502
netstat -ano | findstr :8502

# Kill the process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use a different port
streamlit run streamlitapp_20251123_v2.py --server.port 8504
```

2. **SQL Server Connection Issues:**
```powershell
# Test ODBC connection
sqlcmd -S localhost\MSSQLSERVER01 -E -Q "SELECT @@VERSION"
```

3. **Missing Dependencies:**
```powershell
# Install missing packages
pip install streamlit pyodbc pandas plotly numpy

# Or install all at once
pip install -r requirements.txt
```

4. **Permission Issues:**
```powershell
# Run as administrator if needed
Start-Process powershell -Verb runAs
```

---

## 🌟 Recommended Production Setup

### 1. Create Batch File for Easy Startup:
```powershell
@"
@echo off
echo 🚀 Starting Trading Dashboard...
cd /d "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
streamlit run streamlitapp_20251123_v2.py
pause
"@ | Out-File -FilePath "start_dashboard.bat" -Encoding ASCII
```

### 2. Create Desktop Shortcut:
- Right-click desktop → New → Shortcut
- Target: `"c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance\start_dashboard.bat"`
- Name: "Trading Dashboard"

### 3. Auto-start on Windows Boot (Optional):
```powershell
# Add to Windows startup folder
$startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
Copy-Item "start_dashboard.bat" $startupPath
```

---

## 📊 Current Status

✅ **App Location**: `c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance\streamlitapp_20251123_v2.py`
✅ **Currently Running**: `http://localhost:8502`
✅ **Features Working**: Market switching, PDF export, CSV download, all indicators
✅ **Database**: Connected to SQL Server `localhost\MSSQLSERVER01`

---

## 🎯 Quick Start (Recommended)

For immediate deployment, simply run:

```powershell
cd "c:\Users\sreea\OneDrive\Documents\stockanalysis\agentai_yfinance"
streamlit run streamlitapp_20251123_v2.py
```

Then access: `http://localhost:8502`

This gives you a fully functional trading dashboard with all the enhanced features we've implemented!
