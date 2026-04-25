#!/usr/bin/env python3
"""
MNVPN Quick Reference - Cheat Sheet for Common Tasks

Use this file to quickly access command examples for common operations.
"""

# ============================================================================
# SETUP AND INSTALLATION
# ============================================================================

"""
# Initial setup (one time)
git clone https://github.com/yourusername/mnvpn.git
cd mnvpn

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp .env.example .env
nano .env  # Edit with your credentials

# Initialize database
python3 -c "import asyncio; from database import init_db; asyncio.run(init_db())"

# Run tests
python3 test_integration.py

# Start bot
python3 bot.py
"""


# ============================================================================
# DATABASE QUERIES
# ============================================================================

"""
# Connect to SQLite database
sqlite3 db.sqlite3

# User statistics
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM users WHERE subscription_expiry > datetime('now');

# Payment statistics
SELECT SUM(amount_rubles) FROM payments WHERE status = 'completed';
SELECT COUNT(*) FROM payments WHERE status = 'pending';

# List all payments
SELECT payment_id, user_id, amount_rubles, status, created_at 
FROM payments 
ORDER BY created_at DESC 
LIMIT 20;

# Device statistics
SELECT COUNT(*) FROM devices WHERE is_active = 1;
SELECT user_id, COUNT(*) as device_count FROM devices 
WHERE is_active = 1 GROUP BY user_id;

# Find users with expiring subscriptions (next 7 days)
SELECT user_id, subscription_expiry FROM users 
WHERE subscription_expiry > datetime('now') 
AND subscription_expiry < datetime('now', '+7 days');

# Backup database
sqlite3 db.sqlite3 ".dump" > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
sqlite3 db.sqlite3 < backup_20260416_120000.sql
"""


# ============================================================================
# SYSTEMD SERVICE MANAGEMENT
# ============================================================================

"""
# Check bot status
systemctl status mnvpn-bot.service

# View logs (last 50 lines, follow mode)
journalctl -u mnvpn-bot.service -n 50 -f

# Restart bot
systemctl restart mnvpn-bot.service

# Stop bot
systemctl stop mnvpn-bot.service

# Start bot
systemctl start mnvpn-bot.service

# View service file
cat /etc/systemd/system/mnvpn-bot.service

# Reload systemd daemon after editing service
systemctl daemon-reload
"""


# ============================================================================
# VPN PANEL MANAGEMENT (3X-UI)
# ============================================================================

"""
# Access 3X-UI panel
https://YOUR_SERVER_IP:2053/panel/

# Common operations via 3X-UI:
1. Add Inbound (VPN protocol) - recommended: AmneziaWG
2. Add Client (user) - auto-generate UUID and sub_id
3. View Subscription - copy subscription link
4. Monitor Traffic - see bandwidth usage per client
5. Edit Inbound - adjust port, protocol, obfuscation

# Get inbound list via API
curl -k -X GET 'https://YOUR_SERVER_IP:2053/panel/api/inbounds/list' \\
  -H 'Cookie: ...' 

# Add client programmatically
curl -k -X POST 'https://YOUR_SERVER_IP:2053/panel/api/inbounds/addClient' \\
  -d 'id=1&settings={...}'
"""


# ============================================================================
# CRON JOBS
# ============================================================================

"""
# Edit crontab
crontab -e

# Example cron entries:
# Run cleanup every day at 2 AM
0 2 * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 cleanup_subscriptions.py >> /var/log/mnvpn_cleanup.log 2>&1

# Check pending payments every 10 minutes
*/10 * * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 check_payment_status.py >> /var/log/mnvpn_payment.log 2>&1

# Backup database daily at 3 AM
0 3 * * * sqlite3 /opt/mnvpn/db.sqlite3 ".dump" | gzip > /backups/mnvpn_$(date +\\%Y\\%m\\%d).sql.gz

# View cron logs
grep CRON /var/log/syslog  # Linux
log stream --predicate 'process == "cron"'  # macOS
"""


# ============================================================================
# FIREWALL MANAGEMENT
# ============================================================================

"""
# Check UFW status
sudo ufw status

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow VPN port (example: 52093)
sudo ufw allow 52093/udp
sudo ufw allow 52093/tcp

# Enable firewall
sudo ufw enable

# Disable firewall
sudo ufw disable

# View detailed rules
sudo ufw show added
"""


# ============================================================================
# NGINX REVERSE PROXY (FOR WEBHOOKS)
# ============================================================================

"""
# Test Nginx configuration
sudo nginx -t

# Reload Nginx after config change
sudo systemctl reload nginx

# View access logs (webhooks)
sudo tail -f /var/log/nginx/access.log | grep webhook

# View error logs
sudo tail -f /var/log/nginx/error.log

# Example Nginx config for webhook:
server {
    listen 80;
    server_name your-domain.com;
    
    location /webhook/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Yandex-Checkout-API-Signature $http_x_yandex_checkout_api_signature;
    }
}
"""


# ============================================================================
# SSL/HTTPS WITH LET'S ENCRYPT
# ============================================================================

"""
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot certonly -d your-domain.com --standalone

# Renew certificate (auto, runs daily)
sudo certbot renew

# View certificates
sudo certbot certificates

# Nginx with SSL:
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }
}
"""


# ============================================================================
# TESTING PAYMENTS
# ============================================================================

"""
# Yandex.Kassa Test Cards:
4111 1111 1111 1111  - Successful payment
4000 0000 0000 0002  - Declined payment

# Expiry: Any future date
# CVC: Any 3-digit number

# Test webhook signature verification:
python3 -c "
from payment_service import get_payment_service
import json
import hashlib

service = get_payment_service()
body = json.dumps({'event': 'payment.succeeded'}).encode()
sig = hashlib.sha256(body + service.webhook_secret.encode()).hexdigest()
print(f'Valid signature: {sig}')
"

# Test webhook locally:
curl -X POST http://localhost:8000/webhook/test \\
  -H "Content-Type: application/json" \\
  -d '{"test": "data"}'
"""


# ============================================================================
# MONITORING AND ALERTS
# ============================================================================

"""
# System resources
top  # or 'htop' with better UI
df -h  # Disk space
free -h  # Memory

# Network stats
ss -tulpn | grep python
netstat -tlnp | grep bot

# Database size
du -h db.sqlite3
sqlite3 db.sqlite3 "SELECT page_count * page_size AS size FROM pragma_page_count(), pragma_page_size();"

# Process info
ps aux | grep python
ps aux | grep bot

# Log file sizes
du -h /var/log/mnvpn*.log
du -h /var/log/nginx/*.log

# Clean old logs
find /var/log/ -name "mnvpn*.log" -mtime +30 -delete
"""


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

"""
# Bot not responding
1. Check if running: systemctl status mnvpn-bot.service
2. Check logs: journalctl -u mnvpn-bot.service -n 100
3. Check token: grep BOT_TOKEN .env
4. Restart: systemctl restart mnvpn-bot.service

# VPN clients can't connect
1. Check inbound: curl https://SERVER:2053/panel/api/inbounds/list
2. Check firewall: ufw status
3. Check server port: ss -tulpn | grep 52093
4. Test connectivity: ping VPN_SERVER_IP

# Payments not processing
1. Check webhook logs: tail -f /var/log/nginx/access.log | grep webhook
2. Check payment DB: sqlite3 db.sqlite3 "SELECT * FROM payments ORDER BY created_at DESC LIMIT 5;"
3. Verify credentials: grep YANDEX db.env
4. Check webhook URL in Kassa: https://kassa.yandex.ru/settings/api

# Database corrupted
1. Backup current: cp db.sqlite3 db.sqlite3.corrupted
2. Restore from backup: sqlite3 db.sqlite3 < backup_20260416.sql
3. Or reinitialize: rm db.sqlite3 && python3 bot.py  (WARNING: data loss!)

# High memory usage
1. Check processes: ps aux --sort=-%mem | head -20
2. Restart bot: systemctl restart mnvpn-bot.service
3. Check for leaks: journalctl -u mnvpn-bot.service | grep -i memory
"""


# ============================================================================
# PERFORMANCE OPTIMIZATION
# ============================================================================

"""
# Database optimization
sqlite3 db.sqlite3 "VACUUM;"  # Reclaim space
sqlite3 db.sqlite3 "ANALYZE;"  # Update stats
sqlite3 db.sqlite3 "REINDEX;"  # Rebuild indexes

# Connection pooling (in production)
# Use PostgreSQL with asyncpg for better performance:
DATABASE_URL=postgresql://user:pass@localhost/mnvpn

# Add caching layer
pip install aioredis
# Then use Redis for session caching

# Monitor slow queries
sqlite3 db.sqlite3 ".timer on"
# Then run your queries

# Connection limits
# Edit sshd_config to limit concurrent connections:
grep MaxSessions /etc/ssh/sshd_config
"""


# ============================================================================
# DEPLOYMENT CHECKLIST
# ============================================================================

"""
[ ] VPS provisioned (2+ vCore, 2+ GB RAM)
[ ] OS updated (apt update && apt upgrade)
[ ] SSH key configured
[ ] Firewall rules set (22, 80, 443, VPN ports)
[ ] 3X-UI installed and working
[ ] Python 3.9+ installed
[ ] virtualenv created
[ ] Dependencies installed (pip install -r requirements.txt)
[ ] .env file created with all credentials
[ ] Database initialized (python3 -c "...")
[ ] Yandex.Kassa account created and configured
[ ] Webhook URL added to Kassa settings
[ ] Bot token obtained from @BotFather
[ ] SSL certificate obtained (certbot)
[ ] Nginx reverse proxy configured
[ ] systemd service created and enabled
[ ] Cron jobs scheduled
[ ] Tests passed (python3 test_integration.py)
[ ] Bot started successfully (systemctl start mnvpn-bot.service)
[ ] Webhook server running (python3 webhook_server.py)
[ ] Test payment processed successfully
[ ] Database backup configured
[ ] Monitoring/logging setup
[ ] Documentation updated with server details
"""


# ============================================================================
# USEFUL PYTHON SNIPPETS
# ============================================================================

"""
# Test database connection
import asyncio, aiosqlite
from config import DB_PATH

async def test_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            count = await cursor.fetchone()
            print(f"Users: {count[0]}")

asyncio.run(test_db())


# Test VPN service
import asyncio
from vpn_service import vpn_service

async def test_vpn():
    connected = await vpn_service.login_3xui()
    print(f"3X-UI: {'Connected' if connected else 'Failed'}")

asyncio.run(test_vpn())


# Test payment service
from payment_service import get_payment_service
service = get_payment_service()
print(f"Payment service: {'Ready' if service else 'Not initialized'}")


# Count active subscriptions
import sqlite3
from config import DB_PATH
from datetime import datetime

db = sqlite3.connect(DB_PATH)
cursor = db.execute('''
    SELECT COUNT(*) FROM users 
    WHERE subscription_expiry > ?
''', (datetime.now().isoformat(),))
active = cursor.fetchone()[0]
print(f"Active subscriptions: {active}")
db.close()
"""


# ============================================================================
# USEFUL RESOURCES
# ============================================================================

"""
Official Documentation:
- aiogram: https://docs.aiogram.dev/
- 3X-UI: https://github.com/mhsanaei/3x-ui
- Yandex.Kassa: https://yookassa.ru/developers
- FastAPI: https://fastapi.tiangolo.com/

Testing Tools:
- Telegram Bot Tester: https://core.telegram.org/bots/webapps
- Postman: https://www.postman.com/
- curl: Built-in command-line tool

Monitoring Tools:
- Prometheus: https://prometheus.io/
- Grafana: https://grafana.com/
- New Relic: https://newrelic.com/
- Sentry: https://sentry.io/

VPN Testing:
- IPLeak: https://ipleak.net/
- DNS Leak: https://dnsleaktest.com/
- Speed Test: https://speedtest.net/
"""

# End of quick reference
