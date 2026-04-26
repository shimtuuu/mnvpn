# 🔄 Update to Ultima VPN Pricing Model

## 🌐 What Changed?

### Old Model (Generic VPN)
- Fixed periods: 1/3/6/12 months
- One subscription per user
- Days accumulated when renewing

### New Model (Ultima VPN Style)
- **Price based on device count**: 100₽/month for 1 device, volume discounts for more
- **Period-based discounts**: -10% for 3 months, -15% for 6 months, -20% for 1 year
- **No accumulation**: Each purchase resets the subscription period from NOW
- **Telegram Stars integration**: Pay directly in Telegram

---

## 💰 Pricing Table

### Device Plans (per month)

| Devices | Price (RUB) | Price (Stars) | Savings |
|---------|-------------|---------------|----------|
| 1       | 100₽       | 75⭐          | -        |
| 2       | 180₽       | 135⭐         | 20₽/mo  |
| 3       | 250₽       | 190⭐         | 50₽/mo  |
| 5       | 400₽       | 300⭐         | 100₽/mo |

### Period Discounts

| Period   | Discount | Example (1 device) |
|----------|----------|-----------------|
| 1 month  | 0%       | 100₽ (75⭐)    |
| 3 months | -10%     | 270₽ (203⭐)   |
| 6 months | -15%     | 510₽ (383⭐)   |
| 1 year   | -20%     | 960₽ (720⭐)   |

---

## 🔧 Installation Steps

### 1. Pull latest code

```bash
cd ~/mnvpn
git pull origin main
```

### 2. Run database migration

```bash
python3 migration_ultima_pricing.py
```

**Expected output:**
```
⚡ Running migration on mnvpn.db...
✅ Migration successful! Field 'max_devices' added to users table
🔄 Synced max_devices with existing device_limit values
```

### 3. Restart bot

```bash
sudo systemctl restart mnvpn
# or
pkill -f bot.py && python3 bot.py
```

### 4. Verify pricing

Send `/start` to your bot and navigate to:
**Manage VPN → Buy Subscription**

You should see:
1. Device count selection (1/2/3/5 devices)
2. Period selection (1/3/6/12 months)
3. Two payment options: **⭐ Stars** or **💳 Card**

---

## ✨ New Features

### Telegram Stars Payment

- **Built into Telegram**: No need to leave the app
- **Instant activation**: Keys reactivate immediately after payment
- **No commission**: Telegram doesn't charge fees for bot payments

### Smart Subscription Logic

```python
# Example: User buys 1 month on April 1
expiry = April 30

# User buys another 1 month on April 15
# OLD: expiry = May 30 (days accumulated)
# NEW: expiry = May 15 (30 days from purchase date)
```

### Device Limit Enforcement

- When subscription ends → **all devices disabled**
- After payment → **all devices re-enabled automatically**
- Device limit set by purchased plan (1/2/3/5)

---

## 🛠️ For Developers

### Updated Files

| File | Changes |
|------|--------|
| `config.py` | Added `DEVICE_PLANS` and `SUBSCRIPTION_PERIODS` dictionaries |
| `database.py` | Added `purchase_subscription()` function, updated `extend_subscription()` |
| `handlers.py` | Complete rewrite of subscription flow with Telegram Stars |
| `migration_ultima_pricing.py` | New: Database migration script |

### Key Functions

#### `database.purchase_subscription(user_id, devices, days)`

Purchases subscription with device limit:

```python
await db.purchase_subscription(
    user_id=12345,
    devices=3,  # Max 3 devices
    days=90     # 3 months
)
```

#### Payment Flow

1. User selects device count → `choose_device_count()`
2. User selects period → `choose_period()`
3. User selects payment method → `choose_payment_method()`
4. **Stars**: `pay_with_stars()` → Telegram invoice sent
5. **Card**: `pay_with_card()` → Test payment (replace with real gateway)
6. Payment confirmed → `successful_payment()` → Devices reactivated

### Telegram Stars Invoice Example

```python
await bot.send_invoice(
    chat_id=user_id,
    title="VPN — 3 устройства",
    description="Подписка на 3 мес. для 3 устройств",
    payload=f"sub_{devices}_{days}_{user_id}",
    currency="XTR",  # Telegram Stars
    prices=[LabeledPrice(label="3 устройства, 3 месяца", amount=171)]  # 190*3*0.9
)
```

---

## ❓ FAQ

**Q: What happens to existing users?**
A: Their current subscription remains valid. When they renew, they'll use the new pricing.

**Q: Can I customize prices?**
A: Yes! Edit `DEVICE_PLANS` and `SUBSCRIPTION_PERIODS` in `config.py`.

**Q: How do I integrate real payment provider?**
A: Replace the `pay_with_card()` stub with YooKassa/Stripe integration. See `payment_service.py` for examples.

**Q: Do I need to test Telegram Stars in production?**
A: Stars work in test mode automatically in bot development. In production, real Stars will be charged.

---

## 📊 Analytics

Track pricing performance:

```python
# Most popular device plan
SELECT max_devices, COUNT(*) FROM users GROUP BY max_devices;

# Revenue by payment type
SELECT payment_type, SUM(amount_rubles) FROM payments WHERE status='completed' GROUP BY payment_type;
```

---

## 🐛 Troubleshooting

### Migration fails with "column already exists"

```
✅ This is fine! It means you already ran the migration.
```

### Telegram Stars invoice doesn't appear

- Ensure `provider_token=""` (empty string for Stars)
- Check `currency="XTR"`
- Verify bot has payments enabled via @BotFather

### Devices not reactivating after payment

Check `reactivate_user_clients()` logs:

```python
logger.info(f"Reactivated {enabled_count} devices for user {user_id}")
```

---

**Need help?** Open an issue or contact [@mnvpn_support](https://t.me/mnvpn_support)
