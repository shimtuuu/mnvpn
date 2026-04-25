#!/bin/bash
# Simple 3X-UI Installation (no Docker required)
# Uses direct Go binary installation

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          3X-UI Standalone Installation                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [[ $EUID -ne 0 ]]; then
   echo "❌ Must run as root"
   exit 1
fi

# Create application directory
INSTALL_DIR="/opt/3x-ui"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

echo "Step 1: Downloading 3X-UI..."
# Get latest release
LATEST_VERSION=$(curl -s https://api.github.com/repos/mhsanaei/3x-ui/releases/latest | grep -oP '"tag_name": "\K[^"]*')
echo "Latest version: $LATEST_VERSION"

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARCH_NAME="amd64" ;;
    aarch64) ARCH_NAME="arm64" ;;
    *) echo "❌ Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Download
DOWNLOAD_URL="https://github.com/mhsanaei/3x-ui/releases/download/${LATEST_VERSION}/x-ui-linux-${ARCH_NAME}.tar.gz"
echo "Downloading from: $DOWNLOAD_URL"
wget -q "$DOWNLOAD_URL" -O x-ui.tar.gz

# Extract
tar -xzf x-ui.tar.gz
rm x-ui.tar.gz

echo "✓ 3X-UI downloaded and extracted"
echo ""

echo "Step 2: Setting up systemd service..."
# Create systemd service file
cat > /etc/systemd/system/x-ui.service << 'SYSTEMD_EOF'
[Unit]
Description=3X-UI Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/3x-ui
ExecStart=/opt/3x-ui/x-ui
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

chmod 644 /etc/systemd/system/x-ui.service

echo "✓ Systemd service created"
echo ""

echo "Step 3: Making executable and starting..."
chmod +x /opt/3x-ui/x-ui

systemctl daemon-reload
systemctl enable x-ui.service
systemctl start x-ui.service

# Wait for it to start
sleep 3

echo ""
echo "✓ 3X-UI service started"
echo ""

# Check status
if systemctl is-active --quiet x-ui; then
    echo "✓ Service is RUNNING"
else
    echo "⚠ Service may still be starting..."
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              3X-UI SETUP COMPLETE                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo "📊 ACCESS INFORMATION:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Web Panel: http://49390.koara.live:2053"
echo ""
echo "🔐 Default Credentials:"
echo "   Username: admin"
echo "   Password: admin"
echo ""
echo "⚠️  CHANGE PASSWORD IMMEDIATELY!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📋 NEXT STEPS:"
echo ""
echo "1️⃣ Open browser: http://49390.koara.live:2053"
echo ""
echo "2️⃣ Login with admin/admin"
echo ""
echo "3️⃣ Create AmneziaWG Inbound:"
echo "   • Click 'Inbounds' in left menu"
echo "   • Click 'Add Inbound'"
echo "   • Select Protocol: 'AmneziaWG' or 'WireGuard'"
echo "   • Set Port: 52093"
echo "   • Enable the inbound"
echo "   • Note the Inbound ID (usually 1)"
echo ""
echo "4️⃣ Update MNVPN .env:"
echo "   ssh root@49390.koara.live"
echo "   nano /opt/mnvpn/.env"
echo ""
echo "   Update these lines:"
echo "   VPN_PANEL_URL=http://49390.koara.live:2053"
echo "   VPN_PANEL_USERNAME=admin"
echo "   VPN_PANEL_PASSWORD=admin"
echo "   VPN_INBOUND_ID=1"
echo ""
echo "   (Use Ctrl+O to save, Ctrl+X to exit nano)"
echo ""
echo "5️⃣ Restart bot:"
echo "   systemctl restart mnvpn-bot.service"
echo ""
echo "6️⃣ Test connection:"
echo "   journalctl -u mnvpn-bot.service -f"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✓ Installation complete!"
echo "  Service logs: journalctl -u x-ui -f"
echo "  Service status: systemctl status x-ui"
echo ""
