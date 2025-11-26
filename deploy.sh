#!/bin/bash

# Production deployment script for multizoneus.com
# This script sets up the trading dashboard on a VPS/cloud server

set -e

echo "🚀 Deploying Trading Dashboard to multizoneus.com..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Clone repository (update with your actual repo)
if [ ! -d "trading-dashboard" ]; then
    git clone https://github.com/yourusername/trading-dashboard.git
fi

cd trading-dashboard

# Create environment file
cat > .env << EOF
# Production environment variables
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# API Keys (add your actual keys)
ALPHA_VANTAGE_API_KEY=your_api_key_here
FINNHUB_API_KEY=your_api_key_here

# Domain configuration
DOMAIN=multizoneus.com
EMAIL=admin@multizoneus.com
EOF

# Build and start the application
echo "Building and starting the application..."
docker-compose up -d --build

# Wait for services to start
echo "Waiting for services to start..."
sleep 30

# Check if application is running
if curl -f http://localhost:8501 > /dev/null 2>&1; then
    echo "✅ Trading dashboard is running successfully!"
    echo "🌐 Access your dashboard at: https://multizoneus.com"
else
    echo "❌ Failed to start the application"
    echo "Checking logs..."
    docker-compose logs
    exit 1
fi

# Set up automatic updates (optional)
echo "Setting up automatic updates..."
cat > /etc/cron.d/trading-dashboard-update << EOF
# Update trading dashboard daily at 2 AM
0 2 * * * root cd /path/to/trading-dashboard && git pull && docker-compose up -d --build
EOF

echo "🎉 Deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. Configure your DNS to point multizoneus.com to this server"
echo "2. Add your API keys to the .env file"
echo "3. Customize the dashboard settings in the app"
echo ""
echo "Dashboard URL: https://multizoneus.com"
echo "Traefik Admin: http://your-server-ip:8080"
