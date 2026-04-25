#!/bin/bash
# 3X-UI Installation & Setup Script for MNVPN
# This script installs 3X-UI panel with AmneziaWG protocol support

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          3X-UI Panel Installation for MNVPN               ║"
echo "║    (VPN Panel with AmneziaWG Protocol Support)            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root"
   exit 1
fi

# Detect OS
if [ -f /etc/debian_version ]; then
    OS="debian"
    echo "✓ Detected: Debian/Ubuntu"
elif [ -f /etc/redhat-release ]; then
    OS="redhat"
    echo "✓ Detected: RedHat/CentOS"
else
    echo "❌ Unsupported OS"
    exit 1
fi

echo ""
echo "Step 1: Installing dependencies..."
if [ "$OS" = "debian" ]; then
    apt-get update
    apt-get install -y \
        curl \
        wget \
        git \
        ca-certificates \
        openssl \
        python3 \
        docker.io
    systemctl start docker
    systemctl enable docker
else
    yum update -y
    yum install -y \
        curl \
        wget \
        git \
        ca-certificates \
        openssl \
        python3 \
        docker
    systemctl start docker
    systemctl enable docker
fi

echo "✓ Dependencies installed"
echo ""

echo "Step 2: Installing 3X-UI..."
# Download and run official 3X-UI installation script
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

echo ""
echo "✓ 3X-UI installed successfully!"
echo ""

# Wait for service to be ready
echo "Waiting for 3X-UI service to start..."
sleep 5

# Check if service is running
if systemctl is-active --quiet x-ui; then
    echo "✓ 3X-UI service is running"
else
    echo "⚠ 3X-UI may still be starting. Waiting..."
    sleep 10
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              3X-UI INSTALLATION COMPLETE                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Get local IP
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "📊 3X-UI Access Information:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Web Panel URL: http://$LOCAL_IP:2053"
echo "            or: http://49390.koara.live:2053"
echo ""
echo "Default Login:"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "⚠️  IMPORTANT: Change these credentials immediately!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✓ Next Steps:"
echo "  1. Open browser: http://49390.koara.live:2053"
echo "  2. Login with: admin / admin"
echo "  3. Go to 'Inbounds' menu"
echo "  4. Create new inbound with:"
echo "     - Protocol: AmneziaWG (or Wireguard)"
echo "     - Port: 52093 (or your preferred port)"
echo "     - Click 'Add'"
echo "  5. Get the Inbound ID (usually 1)"
echo "  6. Update /opt/mnvpn/.env with:"
echo "     VPN_PANEL_URL=http://49390.koara.live:2053"
echo "     VPN_PANEL_USERNAME=admin"
echo "     VPN_PANEL_PASSWORD=admin"
echo "     VPN_INBOUND_ID=1"
echo "  7. Restart bot: systemctl restart mnvpn-bot.service"
echo ""

# Provide quick test
echo "Step 3: Testing 3X-UI API..."
echo ""

# Wait a bit more for 3X-UI to fully initialize
sleep 3

# Try to connect to 3X-UI
if curl -s http://127.0.0.1:2053/login -d '{}' > /dev/null 2>&1; then
    echo "✓ 3X-UI API is responding"
else
    echo "⚠ 3X-UI API may still be initializing"
    echo "  Try accessing the web panel in 1-2 minutes"
fi

echo ""
echo "✓ Installation complete! Open http://49390.koara.live:2053 in your browser"
echo ""
