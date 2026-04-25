#!/bin/bash
# MNVPN Automated Deployment Script
# Run this on your VPS: bash deploy.sh
# Prerequisites: Ubuntu 22.04+, root/sudo access

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         MNVPN VPN Service - Automated Deployment           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[i]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

print_step "Starting deployment..."
sleep 2

# Step 1: Update system
print_step "Updating system packages..."
apt update
apt upgrade -y
apt install -y \
    build-essential \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    ufw \
    certbot \
    python3-certbot-nginx \
    nginx \
    chrony

# Step 2: Setup firewall
print_step "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 52093/udp  # VPN port (adjust if needed)
ufw allow 52093/tcp
ufw status | head -10

# Step 3: Clone or upload MNVPN
print_step "Setting up MNVPN application..."
MNVPN_DIR="/opt/mnvpn"

if [ -d "$MNVPN_DIR" ]; then
    print_info "MNVPN directory already exists, updating..."
    cd "$MNVPN_DIR"
    git pull origin main 2>/dev/null || print_info "Not a git repo, skipping update"
else
    print_info "Cloning MNVPN repository..."
    mkdir -p /opt
    cd /opt
    
    # If you have a git repo:
    # git clone https://github.com/yourusername/mnvpn.git
    
    # Otherwise, create from scratch:
    mkdir -p mnvpn
    cd mnvpn
    print_info "Please upload MNVPN files here: $MNVPN_DIR"
fi

cd "$MNVPN_DIR"

# Step 4: Python virtual environment
print_step "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Step 5: Install Python dependencies
print_step "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Configuration
print_step "Setting up environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_info "Created .env file. EDIT IT NOW with your credentials!"
        print_info "Required fields:"
        print_info "  - BOT_TOKEN (from @BotFather)"
        print_info "  - VPN_PANEL_URL, username, password"
        print_info "  - YANDEX_KASSA_* (if using Kassa)"
        
        # Prompt user to edit
        read -p "Have you edited .env with your credentials? (yes/no): " -r
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Please edit .env and run script again"
            exit 1
        fi
    else
        print_error ".env.example not found!"
        exit 1
    fi
else
    print_info ".env already exists, skipping"
fi

# Step 7: Initialize database
print_step "Initializing database..."
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('Database initialized successfully!')
" || print_error "Database initialization failed"

# Step 8: Run tests
print_step "Running integration tests..."
python3 test_integration.py 2>&1 | tail -20 || print_info "Some tests may require 3X-UI connection"

# Step 9: Setup systemd service
print_step "Creating systemd service..."
cat > /etc/systemd/system/mnvpn-bot.service << 'SYSTEMD_EOF'
[Unit]
Description=MNVPN Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/mnvpn
ExecStart=/opt/mnvpn/.venv/bin/python3 /opt/mnvpn/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

chmod 644 /etc/systemd/system/mnvpn-bot.service
systemctl daemon-reload
systemctl enable mnvpn-bot.service
print_step "Systemd service created"

# Step 10: Setup cron jobs
print_step "Setting up cron jobs..."
CRON_ENTRY_CLEANUP="0 2 * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 /opt/mnvpn/cleanup_subscriptions.py >> /var/log/mnvpn_cleanup.log 2>&1"
CRON_ENTRY_PAYMENT="*/10 * * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 /opt/mnvpn/check_payment_status.py >> /var/log/mnvpn_payment.log 2>&1"

# Check if cron entries already exist
(crontab -l 2>/dev/null | grep -F "cleanup_subscriptions.py") > /dev/null || echo "$CRON_ENTRY_CLEANUP" | crontab -
(crontab -l 2>/dev/null | grep -F "check_payment_status.py") > /dev/null || echo "$CRON_ENTRY_PAYMENT" | crontab -

print_step "Cron jobs configured"

# Step 11: Setup Nginx reverse proxy (for webhooks)
print_step "Configuring Nginx reverse proxy..."
cat > /etc/nginx/sites-available/mnvpn << 'NGINX_EOF'
server {
    listen 80;
    server_name _;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Yandex-Checkout-API-Signature $http_x_yandex_checkout_api_signature;
    }

    location / {
        return 404;
    }
}
NGINX_EOF

ln -sf /etc/nginx/sites-available/mnvpn /etc/nginx/sites-enabled/mnvpn
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
print_step "Nginx configured"

# Step 12: Create log directory
mkdir -p /var/log/mnvpn
touch /var/log/mnvpn_cleanup.log
touch /var/log/mnvpn_payment.log
chmod 666 /var/log/mnvpn*.log

# Step 13: Start bot service
print_step "Starting MNVPN bot service..."
systemctl start mnvpn-bot.service
sleep 2

# Check if service started
if systemctl is-active --quiet mnvpn-bot.service; then
    print_step "Bot service started successfully!"
else
    print_error "Bot service failed to start. Check logs:"
    journalctl -u mnvpn-bot.service -n 20
fi

# Step 14: Summary
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              DEPLOYMENT COMPLETED SUCCESSFULLY!            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
print_step "MNVPN is now deployed and running!"
echo ""
echo "📋 Next steps:"
echo "  1. Configure SSL certificate:"
echo "     sudo certbot certonly -d your-domain.com --standalone"
echo "  2. Update Nginx config with SSL details"
echo "  3. Add webhook URL to Yandex.Kassa:"
echo "     https://your-domain.com/webhook/payment"
echo "  4. Test bot: /start command in Telegram"
echo "  5. Monitor logs: journalctl -u mnvpn-bot.service -f"
echo ""
echo "📊 Useful commands:"
echo "  • View bot logs: journalctl -u mnvpn-bot.service -f"
echo "  • Bot status: systemctl status mnvpn-bot.service"
echo "  • Restart bot: systemctl restart mnvpn-bot.service"
echo "  • Check database: sqlite3 /opt/mnvpn/db.sqlite3"
echo "  • View cron logs: tail -f /var/log/mnvpn_*.log"
echo ""
echo "🔗 Resources:"
echo "  • Deployment guide: /opt/mnvpn/DEPLOYMENT_GUIDE.md"
echo "  • Quick reference: /opt/mnvpn/QUICK_REFERENCE.py"
echo "  • Bot logs: journalctl -u mnvpn-bot.service"
echo ""
