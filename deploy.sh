#!/bin/bash
#
# Altcoin Short Monitoring System - Deployment Script
# For Ubuntu 20.04/22.04/24.04
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN} Altcoin Short Monitor - Deployment${NC}"
echo -e "${GREEN}======================================${NC}"

# Configuration
INSTALL_DIR="/opt/shiit_short"
SERVICE_NAME="shiit-monitor"
REPO_URL="${REPO_URL:-https://github.com/YOUR_REPO/shiit_short.git}"
BRANCH="${BRANCH:-main}"
USER="${DEPLOY_USER:-$USER}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${YELLOW}Warning: Running as root. Service will run as 'ubuntu' user.${NC}"
    USER="ubuntu"
fi

echo ""
echo "Install directory: $INSTALL_DIR"
echo "Service name: $SERVICE_NAME"
echo "Run as user: $USER"
echo ""

# Step 1: Install system dependencies
echo -e "${GREEN}[1/6] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git jq

# Verify Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# Step 2: Clone or update repository
echo -e "${GREEN}[2/6] Setting up repository...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists, updating..."
    cd "$INSTALL_DIR"
    sudo -u $USER git fetch origin
    sudo -u $USER git reset --hard origin/$BRANCH
else
    echo "Cloning repository..."
    sudo git clone -b $BRANCH "$REPO_URL" "$INSTALL_DIR"
    sudo chown -R $USER:$USER "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Step 3: Setup Python virtual environment
echo -e "${GREEN}[3/6] Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Create log directories
echo -e "${GREEN}[4/6] Creating directories...${NC}"
mkdir -p logs/signals
chown -R $USER:$USER logs

# Step 5: Create systemd service
echo -e "${GREEN}[5/6] Creating systemd service...${NC}"
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Altcoin Short Monitoring System
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/bin
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Resource limits
MemoryLimit=512M
CPUQuota=50%

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$INSTALL_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

# Step 6: Enable and start service
echo -e "${GREEN}[6/6] Enabling and starting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME

# Check if already running
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo "Service is running, restarting..."
    sudo systemctl restart $SERVICE_NAME
else
    sudo systemctl start $SERVICE_NAME
fi

# Wait for service to start
sleep 3

# Show status
echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN} Deployment Complete!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Check service status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}Service status: RUNNING${NC}"
else
    echo -e "${RED}Service status: FAILED${NC}"
    echo "Check logs with: sudo journalctl -u $SERVICE_NAME -n 50"
    exit 1
fi

echo ""
echo "Useful commands:"
echo "  View logs:     sudo journalctl -u $SERVICE_NAME -f"
echo "  Stop service:  sudo systemctl stop $SERVICE_NAME"
echo "  Restart:       sudo systemctl restart $SERVICE_NAME"
echo "  View signals:  tail -f $INSTALL_DIR/logs/signals/pumps_\$(date +%Y%m%d).jsonl"
echo ""
echo -e "${YELLOW}Note: Edit $INSTALL_DIR/config/config.yaml to customize settings${NC}"
echo ""
