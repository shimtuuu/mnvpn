# 🌐 3X-UI + MNVPN Quick Setup Guide

## ✅ 3X-UI Installation Complete

**Status:** Running on 49390.koara.live:2053
**Service:** x-ui (systemd)
**Version:** v2.8.11 (latest)

---

## 📋 Step 1: Access 3X-UI Web Panel

Open in browser:
```
http://49390.koara.live:2053
```

Login with:
- **Username:** `admin`
- **Password:** `admin`

---

## 🔧 Step 2: Create AmneziaWG Inbound

1. Click **"Inbounds"** in left sidebar
2. Click **"Add Inbound"** button
3. Fill in settings:
   - **Protocol:** Select `AmneziaWG` (if available) or `WireGuard`
   - **Port:** `52093` (standard VPN port)
   - **Status:** Enable
4. Click **"Add"**
5. **Note down the Inbound ID** (usually `1`)

### Screenshot Guide:
```
Left Sidebar:
  └─ Inbounds
      └─ [Add Inbound]
         ├─ Protocol: AmneziaWG ✓
         ├─ Port: 52093
         ├─ Enable: ✓
         └─ [Add]
```

---

## 🔑 Step 3: Update MNVPN Configuration

SSH into VPS:
```bash
ssh root@49390.koara.live
```

Edit .env file:
```bash
nano /opt/mnvpn/.env
```

Find and update these lines:
```env
VPN_PANEL_URL=http://49390.koara.live:2053
VPN_PANEL_USERNAME=admin
VPN_PANEL_PASSWORD=admin
VPN_INBOUND_ID=1
VPN_SERVER_IP=49390.koara.live
```

**To save in nano:**
- Press: `Ctrl + O` (write out)
- Press: `Enter` (confirm)
- Press: `Ctrl + X` (exit)

---

## 🚀 Step 4: Restart MNVPN Bot

```bash
systemctl restart mnvpn-bot.service
```

Check status:
```bash
systemctl status mnvpn-bot.service
```

View logs:
```bash
journalctl -u mnvpn-bot.service -f
```

---

## 🧪 Step 5: Test the Integration

### In Telegram:

1. Message your bot (with the BOT_TOKEN from .env)
2. Send: `/start`
3. Click: **"🔑 Получить VPN ключ"** (Get VPN Key)
4. Bot should generate a VPN configuration

### Check Database:

```bash
sqlite3 /opt/mnvpn/db.sqlite3
SELECT * FROM users;
SELECT * FROM devices LIMIT 5;
.exit
```

### View 3X-UI Panel:

Go to http://49390.koara.live:2053 → **"Clients"**
You should see new VPN clients appearing as users register

---

## 🔐 Security: Change Admin Password

⚠️ **VERY IMPORTANT:** Change the default admin password!

1. Go to 3X-UI: http://49390.koara.live:2053
2. Click **"Settings"** or **"Dashboard"**
3. Find **"Change Password"** option
4. Set a strong password
5. Save

---

## 📊 Useful Commands

### Check 3X-UI Service:
```bash
systemctl status x-ui
journalctl -u x-ui -f
```

### Restart 3X-UI:
```bash
systemctl restart x-ui
```

### Check MNVPN Bot:
```bash
systemctl status mnvpn-bot.service
journalctl -u mnvpn-bot.service -n 50
```

### Monitor Both Services:
```bash
# Terminal 1:
journalctl -u x-ui -f

# Terminal 2:
journalctl -u mnvpn-bot.service -f
```

### Access 3X-UI API Directly:
```bash
# Test login
curl -X POST http://127.0.0.1:2053/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Get inbounds
curl http://127.0.0.1:2053/api/inbounds -H "Cookie: PHPSESSID=your_session"
```

---

## 🎯 Connectivity Check

### From MNVPN Bot:
The bot should now be able to:
1. ✓ Connect to 3X-UI panel
2. ✓ Create clients on AmneziaWG inbound
3. ✓ Generate VPN configuration
4. ✓ Return subscription link to users

### Expected Flow:
```
User /start
  ↓
MNVPN Bot
  ├─ Register in database
  ├─ Send main menu
  └─ Wait for action
  
User clicks "Get VPN"
  ↓
MNVPN Bot
  ├─ Connect to 3X-UI API
  ├─ Create client with UUID
  ├─ Get subscription URL
  ├─ Generate QR code
  └─ Send to user
```

---

## 🚨 Troubleshooting

### 3X-UI won't start:
```bash
systemctl restart x-ui
sleep 3
journalctl -u x-ui -n 20
```

### Can't access web panel:
- Check firewall: `ufw status`
- Add rule: `ufw allow 2053/tcp`
- Restart: `systemctl restart x-ui`

### Bot can't connect to 3X-UI:
- Check URL in .env: Should be `http://49390.koara.live:2053`
- Check credentials: username/password must match 3X-UI
- Check logs: `journalctl -u mnvpn-bot.service -n 50`

### No clients appearing in 3X-UI:
- Check VPN_INBOUND_ID in .env (should be `1`)
- Verify inbound is enabled in 3X-UI panel
- Check bot logs for errors

### Password reset (if forgotten):
```bash
# SSH to VPS
ssh root@49390.koara.live

# Reset to default
cd /opt/3x-ui
./x-ui -username admin -password admin

# Restart
systemctl restart x-ui
```

---

## 📈 Next Steps

1. ✅ 3X-UI installed
2. ✅ AmneziaWG inbound created
3. ✅ MNVPN bot connected
4. ⬜ Test first user subscription
5. ⬜ Setup Yandex.Kassa payments (production)
6. ⬜ Setup SSL certificate with domain
7. ⬜ Configure webhook URL for payments
8. ⬜ Monitor metrics and scale

---

## 📞 Support

### Logs to check:
```bash
# 3X-UI errors
journalctl -u x-ui -f

# Bot connection issues
journalctl -u mnvpn-bot.service -f

# System errors
dmesg | tail -20
```

### Database queries:
```bash
sqlite3 /opt/mnvpn/db.sqlite3 "SELECT * FROM users;"
sqlite3 /opt/mnvpn/db.sqlite3 "SELECT * FROM devices;"
sqlite3 /opt/mnvpn/db.sqlite3 "SELECT * FROM payments;"
```

### VPS info:
```bash
hostname -I              # IP address
df -h                    # Disk usage
free -h                  # Memory
ps aux | grep -E "(x-ui|mnvpn)"  # Running processes
```

---

## ✨ Success Criteria

When fully working, you should see:

✅ 3X-UI panel accessible at http://49390.koara.live:2053
✅ MNVPN bot responding to `/start` command
✅ Bot can create clients in 3X-UI
✅ Users receiving VPN configuration links
✅ Users able to connect to VPN
✅ No errors in logs

---

📝 **Last Updated:** April 16, 2026
🔧 **Version:** 3X-UI v2.8.11 + MNVPN 1.0
