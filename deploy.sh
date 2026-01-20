#!/bin/bash
# Deployment script for Client Health Monitor
# Run this on your Linux server after copying files

set -e  # Exit on error

echo "=========================================="
echo "Client Health Monitor - Deployment Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}Error: Do not run this script as root${NC}"
    echo "Run as regular user with sudo privileges"
    exit 1
fi

# Get current user
CURRENT_USER=$(whoami)
APP_DIR="/opt/client-monitor"

echo -e "${YELLOW}Step 1: Installing system dependencies...${NC}"
if command -v apt-get &> /dev/null; then
    # Ubuntu/Debian
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
    echo -e "${GREEN}✓ Dependencies installed (Ubuntu/Debian)${NC}"
elif command -v yum &> /dev/null; then
    # CentOS/RHEL
    sudo yum update -y
    sudo yum install -y python3 python3-pip
    echo -e "${GREEN}✓ Dependencies installed (CentOS/RHEL)${NC}"
else
    echo -e "${RED}Error: Unsupported Linux distribution${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Creating application directory...${NC}"
sudo mkdir -p $APP_DIR
sudo chown $CURRENT_USER:$CURRENT_USER $APP_DIR
echo -e "${GREEN}✓ Directory created: $APP_DIR${NC}"

echo ""
echo -e "${YELLOW}Step 3: Copying application files...${NC}"
if [ -f "/tmp/monitor_app.tar.gz" ]; then
    cd $APP_DIR
    tar -xzf /tmp/monitor_app.tar.gz
    echo -e "${GREEN}✓ Files extracted${NC}"
else
    echo -e "${RED}Error: /tmp/monitor_app.tar.gz not found${NC}"
    echo "Please copy the archive to the server first:"
    echo "  scp monitor_app.tar.gz username@server:/tmp/"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 4: Setting up Python virtual environment...${NC}"
cd $APP_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"

echo ""
echo -e "${YELLOW}Step 5: Creating .env file...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    cat > $APP_DIR/.env << 'EOF'
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Flask Configuration
FLASK_ENV=production
SECRET_KEY=change-this-to-a-random-secret-key
EOF
    echo -e "${YELLOW}⚠ .env file created with default values${NC}"
    echo -e "${YELLOW}⚠ IMPORTANT: Edit $APP_DIR/.env with your actual credentials${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

echo ""
echo -e "${YELLOW}Step 6: Initializing database...${NC}"
cd $APP_DIR
source venv/bin/activate
mkdir -p instance
export FLASK_APP=app.py
flask db init 2>/dev/null || echo "Database already initialized"
flask db migrate -m "Initial migration" 2>/dev/null || echo "Migration already exists"
flask db upgrade
echo -e "${GREEN}✓ Database initialized${NC}"

echo ""
echo -e "${YELLOW}Step 7: Creating systemd service...${NC}"
sudo tee /etc/systemd/system/client-monitor.service > /dev/null << EOF
[Unit]
Description=Client Health Monitor Flask Application
After=network.target

[Service]
Type=notify
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn -c gunicorn_config.py wsgi:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
echo -e "${GREEN}✓ Systemd service created${NC}"

echo ""
echo -e "${YELLOW}Step 8: Starting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable client-monitor
sudo systemctl start client-monitor
sleep 2
echo -e "${GREEN}✓ Service started${NC}"

echo ""
echo -e "${YELLOW}Step 9: Checking service status...${NC}"
if sudo systemctl is-active --quiet client-monitor; then
    echo -e "${GREEN}✓ Service is running!${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Check logs with: sudo journalctl -u client-monitor -n 50"
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 10: Configuring firewall...${NC}"
if command -v ufw &> /dev/null; then
    sudo ufw allow 5001/tcp 2>/dev/null || true
    echo -e "${GREEN}✓ Firewall configured (ufw)${NC}"
elif command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --permanent --add-port=5001/tcp 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
    echo -e "${GREEN}✓ Firewall configured (firewalld)${NC}"
else
    echo -e "${YELLOW}⚠ No firewall detected, skipping${NC}"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Application is running at:"
echo "  http://$(hostname -I | awk '{print $1}'):5001"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status client-monitor   # Check status"
echo "  sudo systemctl restart client-monitor  # Restart service"
echo "  sudo journalctl -u client-monitor -f   # View logs"
echo "  tail -f $APP_DIR/app.log              # View app logs"
echo ""
echo -e "${YELLOW}IMPORTANT: Edit $APP_DIR/.env with your email credentials!${NC}"
echo ""

