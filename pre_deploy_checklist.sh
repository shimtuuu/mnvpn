#!/bin/bash
# Pre-deployment checklist for VPS

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    MNVPN Pre-Deployment Checklist (Complete This First)    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

CHECKS_PASSED=0
CHECKS_TOTAL=0

check_item() {
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    echo ""
    echo "[$CHECKS_TOTAL] $1"
    read -p "   ✓ Complete? (yes/no): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        echo "   ✅ Done"
    else
        echo "   ⏭️  Skipped (required for deployment)"
    fi
}

check_item "1️⃣ VPS PROVISIONING
   □ Provider: Hetzner / DigitalOcean / AWS / Yandex.Cloud
   □ OS: Ubuntu 22.04 LTS
   □ RAM: 2GB+ (1GB minimum)
   □ CPU: 2+ cores
   □ Disk: 20GB+ SSD
   □ Connection test: ping <your_vps_ip>"

check_item "2️⃣ TELEGRAM BOT TOKEN
   □ Message @BotFather on Telegram
   □ Command: /newbot
   □ Get token: 123456789:ABCDefGhIjKlMnOpQrStUvWxYz...
   □ Store it safely"

check_item "3️⃣ VPN PANEL (3X-UI) SETUP
   □ SSH into VPS
   □ Install 3X-UI: bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
   □ Access panel: http://your_vps_ip:2053
   □ Default login: admin/admin (CHANGE THIS!)
   □ Create inbound: Protocol=AmneziaWG, Port=52093
   □ Get panel URL, username, password"

check_item "4️⃣ YANDEX.KASSA SETUP (for payments)
   □ Create account at https://kassa.yandex.ru (requires Russian bank account)
   □ Complete KYC verification (1-3 days)
   □ Get Shop ID and API Key
   □ Get Webhook Secret
   □ Enable test mode for testing
   └─ TEST CARD: 4111 1111 1111 1111, exp: any future, cvv: 000"

check_item "5️⃣ DOMAIN NAME (recommended)
   □ Domain registered (domain.com)
   □ DNS A record points to VPS IP
   □ DNS propagated (test: nslookup domain.com)
   └─ This enables HTTPS and webhook reliability"

check_item "6️⃣ ENVIRONMENT FILE (.env)
   □ Copy template: cp .env.example .env
   □ Edit with your values:
     □ BOT_TOKEN=<your_telegram_token>
     □ VPN_PANEL_URL=http://your_vps_ip:2053
     □ VPN_PANEL_USERNAME=admin
     □ VPN_PANEL_PASSWORD=your_password
     □ YANDEX_KASSA_SHOP_ID=<shop_id>
     □ YANDEX_KASSA_API_KEY=<api_key>
     □ YANDEX_KASSA_WEBHOOK_SECRET=<webhook_secret>
     □ APP_DOMAIN=your-domain.com (or IP)"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    CHECKLIST SUMMARY                       ║"
echo "║              $CHECKS_PASSED/$CHECKS_TOTAL items completed                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ $CHECKS_PASSED -ge 4 ]; then
    echo "✅ You're ready for deployment!"
    echo ""
    echo "📝 Upload MNVPN files to your VPS:"
    echo "   scp -r /path/to/mnvpn root@your_vps_ip:/opt/"
    echo ""
    echo "🚀 Then run on VPS:"
    echo "   ssh root@your_vps_ip"
    echo "   cd /opt/mnvpn"
    echo "   bash deploy.sh"
    echo ""
else
    echo "⚠️  Please complete all prerequisite items before deploying"
    echo ""
fi
