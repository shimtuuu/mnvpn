# 🚀 QUICK DEPLOYMENT GUIDE

## 3-Step Deployment

### Step 1: Complete Pre-Deployment Checklist (10-30 min)
```bash
bash pre_deploy_checklist.sh
```
You need:
- [ ] VPS with Ubuntu 22.04 (2GB RAM, 2+ cores)
- [ ] Telegram bot token from @BotFather
- [ ] 3X-UI installed on VPS with AmneziaWG inbound
- [ ] Yandex.Kassa account (optional, for production)
- [ ] Domain name (optional, but recommended)

### Step 2: Prepare Files (5 min)
```bash
# Copy current MNVPN folder to your VPS
# Replace YOUR_VPS_IP with your actual IP

# Option A: Via SCP
scp -r /Users/sharonshalmiev/Desktop/mnvpn root@YOUR_VPS_IP:/opt/

# Option B: Via Git (if you have a repo)
ssh root@YOUR_VPS_IP
cd /opt
git clone https://github.com/yourusername/mnvpn.git
```

### Step 3: Run Automated Deployment (5-10 min)
```bash
ssh root@YOUR_VPS_IP

# Navigate to app folder
cd /opt/mnvpn

# Make deployment script executable
chmod +x deploy.sh

# Review your .env file is correct
nano .env

# Run deployment (fully automated!)
bash deploy.sh
```

That's it! Bot should be running.

## Verify Deployment

### Check Bot Status
```bash
# SSH into VPS, then:
systemctl status mnvpn-bot.service

# View live logs
journalctl -u mnvpn-bot.service -f
```

### Test Bot in Telegram
1. Message your bot
2. Send `/start`
3. Should see menu with options
4. Try `/help`

### Check Database
```bash
sqlite3 /opt/mnvpn/db.sqlite3

# List tables:
.tables

# Check users:
SELECT * FROM users;
```

### Test Payment Webhook (if Kassa configured)
```bash
# From VPS:
curl -X POST http://127.0.0.1:8000/webhook/test

# Should return: {"status": "ok"}
```

## SSL/HTTPS Setup (Recommended for Webhooks)

```bash
# SSH into VPS first
ssh root@YOUR_VPS_IP

# Install Let's Encrypt certificate
certbot certonly -d your-domain.com --standalone

# Update Nginx config with SSL
sudo nano /etc/nginx/sites-available/mnvpn

# Add these server blocks:
# server {
#     listen 443 ssl http2;
#     server_name your-domain.com;
#     
#     ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
#     
#     location /webhook/ {
#         proxy_pass http://127.0.0.1:8000;
#         ...
#     }
# }

# Test and reload
sudo nginx -t
sudo systemctl reload nginx

# Update .env with HTTPS URL
nano .env
# Change: APP_DOMAIN=your-domain.com
```

## Troubleshooting

### Bot won't start
```bash
# Check error logs
journalctl -u mnvpn-bot.service -n 50

# Common issues:
# 1. BOT_TOKEN invalid → get new token from @BotFather
# 2. Can't connect to 3X-UI → check VPN_PANEL_URL and credentials
# 3. Database locked → delete .venv and reinstall
```

### 3X-UI connection error
```bash
# SSH to VPS and test 3X-UI
curl -X POST http://your_vps_ip:2053/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}'

# If fails: restart 3X-UI service
systemctl restart x-ui
```

### Payment webhook not working
```bash
# Check Nginx is forwarding correctly
curl -v http://127.0.0.1/webhook/test

# Check Yandex.Kassa webhook URL in dashboard
# Should be: https://your-domain.com/webhook/payment

# View webhook logs
tail -f /var/log/mnvpn_*.log
```

## Useful Commands

```bash
# View bot logs (live)
journalctl -u mnvpn-bot.service -f

# Restart bot
systemctl restart mnvpn-bot.service

# Stop bot
systemctl stop mnvpn-bot.service

# Start bot
systemctl start mnvpn-bot.service

# Check database
sqlite3 /opt/mnvpn/db.sqlite3 "SELECT * FROM users;"

# View cleanup script logs
tail -f /var/log/mnvpn_cleanup.log

# View payment check logs
tail -f /var/log/mnvpn_payment.log

# Check cron jobs
crontab -l

# Backup database
sqlite3 /opt/mnvpn/db.sqlite3 ".dump" > mnvpn_backup.sql

# View Nginx errors
tail -f /var/log/nginx/error.log
```

## Next Steps After Deployment

1. **Add webhook URL to Yandex.Kassa dashboard**
   - Settings → Webhooks → Add URL
   - URL: `https://your-domain.com/webhook/payment`
   - Events: `payment.succeeded`, `payment.canceled`

2. **Test payment flow**
   - Message bot: `/start`
   - Click: "💳 Купить подписку"
   - Use test card: `4111 1111 1111 1111`

3. **Setup monitoring** (optional)
   - Monitor Telegram: get notifications when users join
   - Monitor database: check user count regularly
   - Monitor VPS: CPU, RAM, disk usage

4. **Scale when ready**
   - Add more servers (update DEPLOYMENT_GUIDE.md)
   - Migrate to PostgreSQL
   - Add analytics

## Need Help?

- 📖 Full guide: `/opt/mnvpn/DEPLOYMENT_GUIDE.md`
- 🔍 Quick reference: `/opt/mnvpn/QUICK_REFERENCE.py`
- 📋 Implementation details: `/opt/mnvpn/IMPLEMENTATION_SUMMARY.md`
