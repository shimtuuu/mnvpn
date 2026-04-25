# MNVPN - Полное руководство по развертыванию платного VPN-сервиса

## Оглавление
1. [Требования и закупка сервера](#требования-и-закупка-сервера)
2. [Установка и настройка VPS](#установка-и-настройка-vps)
3. [Установка 3X-UI VPN панели](#установка-3x-ui-vpn-панели)
4. [Развертывание приложения](#развертывание-приложения)
5. [Конфигурация платежей](#конфигурация-платежей)
6. [Запуск и тестирование](#запуск-и-тестирование)
7. [Масштабирование](#масштабирование)

---

## Требования и закупка сервера

### Минимальные требования для MVP (10-50 пользователей):
- **CPU**: 2 vCore
- **RAM**: 2-4 GB
- **Disk**: 40-50 GB SSD
- **Bandwidth**: 1-5 Gbps (зависит от нагрузки)
- **OS**: Ubuntu 22.04 LTS

### Рекомендуемые VPS провайдеры (поддерживают российских пользователей):
- **Hetzner Cloud** (Финляндия/Германия)
- **DigitalOcean** (глобально)
- **Vultr** (глобально)
- **Linode** (глобально)
- **Azure** (если нужна локальная регистрация)

### Примерная стоимость:
- Basic (2 vCore, 2GB RAM): $5-10/мес
- Standard (4 vCore, 4GB RAM): $15-25/мес
- Premium (8 vCore, 8GB RAM): $40-60/мес

**Расчет прибыли:**
- Цена подписки: 100₽ (≈1.2$) за 30 дней
- Если 100 активных пользователей: 100 × 100₽ = 10,000₽/месяц ≈ $120
- Минус затраты на сервер ($10): прибыль ≈ $110/месяц

---

## Установка и настройка VPS

### Шаг 1: Подключение к серверу

```bash
# Используя SSH ключ (рекомендуется)
ssh -i ~/.ssh/vps_key.pem root@YOUR_SERVER_IP

# Или через пароль
ssh root@YOUR_SERVER_IP
```

### Шаг 2: Обновление системы

```bash
apt update && apt upgrade -y
apt install -y build-essential curl wget git python3 python3-pip
```

### Шаг 3: Настройка firewall

```bash
# Установка UFW
apt install -y ufw

# Разрешить SSH
ufw allow 22/tcp

# Разрешить HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Разрешить VPN портов (откроем позже в 3X-UI)
# ufw allow 10000:65535/udp
# ufw allow 10000:65535/tcp

# Включить firewall
ufw enable
```

### Шаг 4: Настройка swap (если нужно)

```bash
# Создать 2GB swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Добавить в fstab для автозагрузки
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Шаг 5: Настройка NTP (синхронизация времени)

```bash
apt install -y chrony
systemctl restart chrony
timedatectl set-timezone UTC  # Или ваш часовой пояс
```

---

## Установка 3X-UI VPN панели

### Шаг 1: Загрузка и запуск инсталлера

```bash
# Создать директорию
mkdir -p /opt/3x-ui && cd /opt/3x-ui

# Скачать и запустить установщик
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

# Следовать инструкциям:
# - Выбрать номер протокола (выбрать 1 - Xray)
# - Задать пароль админа
# - Задать прослушиваемый порт (по умолчанию 2053)
```

### Шаг 2: Доступ к панели

```
URL: https://YOUR_SERVER_IP:2053/panel/
Логин: admin
Пароль: (тот что вы ввели)
```

### Шаг 3: Создание входящего подключения (Inbound)

В панели 3X-UI:
1. Перейдите в "Inbound list"
2. Нажмите "Add inbound"
3. Настройте:
   - **Protocol**: AmneziaWG
   - **Tag**: amnezia (или любой другой)
   - **Listen IP**: 0.0.0.0
   - **Port**: 52093 (или любой другой, не системный)
   - **MTU**: 1280
   - **Obfuscation**: Включить
4. Сохраните и запомните `Inbound ID` (нужен для конфига бота)

### Шаг 4: Получение Secret URL для подписок

В 3X-UI -> Subscription:
1. Скопируйте "Base URL" (обычно `https://IP:2096`)
2. Скопируйте Secret Token (используется в конфиге бота)

---

## Развертывание приложения

### Шаг 1: Клонирование репозитория

```bash
cd /opt
git clone https://github.com/yourusername/mnvpn.git
cd mnvpn
```

### Шаг 2: Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Шаг 3: Создание .env файла

```bash
cat > .env << 'EOF'
# Bot
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE

# Database
DB_PATH=/opt/mnvpn/db.sqlite3

# VPN Panel (3X-UI)
VPN_PANEL_URL=https://YOUR_SERVER_IP:2053
VPN_PANEL_USERNAME=admin
VPN_PANEL_PASSWORD=YOUR_ADMIN_PASSWORD

# Yandex.Kassa (see section below)
YANDEX_KASSA_SHOP_ID=YOUR_SHOP_ID
YANDEX_KASSA_API_KEY=YOUR_API_KEY
YANDEX_KASSA_WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET

# VPN Service
VPN_SUBSCRIPTION_PRICE=100
VPN_DEVICE_PRICE=100
SUBSCRIPTION_DAYS=30

# Application
APP_DOMAIN=https://your-domain.com
LOG_LEVEL=INFO
EOF

chmod 600 .env
```

### Шаг 4: Инициализация базы данных

```bash
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('Database initialized!')
"
```

---

## Конфигурация платежей

### Вариант 1: Yandex.Kassa (рекомендуется для РФ)

#### Регистрация:
1. Перейдите на https://kassa.yandex.ru
2. Зарегистрируйте компанию
3. Заполните все документы (может занять 1-3 дня)
4. Получите реквизиты:
   - Shop ID
   - API Key
   - Webhook Secret

#### Настройка вебхука:
1. В личном кабинете Yandex.Kassa
2. Перейдите в "Настройки" -> "Уведомления"
3. Добавьте вебхук:
   - URL: `https://your-domain.com/webhook/payment`
   - Используйте POST
   - Подтвердите в settings

### Вариант 2: QIWI (альтернатива)

```python
# Замените payment_service.py на QIWI интеграцию:
# https://developer.qiwi.com/
```

### Вариант 3: Криптовалюты (Stripe -> USDT)

```python
# Используйте Stripe API для USDT платежей
# https://stripe.com/docs/payments/accept-a-payment
```

---

## Запуск и тестирование

### Шаг 1: Тестирование подключения к VPN панели

```bash
source .venv/bin/activate
python3 -c "
import asyncio
from vpn_service import vpn_service

async def test():
    result = await vpn_service.login_3xui()
    print('3X-UI connection:', 'OK' if result else 'FAILED')

asyncio.run(test())
"
```

### Шаг 2: Запуск бота в фоне (тестирование)

```bash
source .venv/bin/activate
python3 bot.py
```

Проверьте в Telegram: напишите `/start` вашему боту

### Шаг 3: Настройка systemd сервиса

```bash
cat > /etc/systemd/system/mnvpn-bot.service << 'EOF'
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
EOF

# Запустить сервис
systemctl daemon-reload
systemctl enable mnvpn-bot.service
systemctl start mnvpn-bot.service

# Проверить статус
systemctl status mnvpn-bot.service
journalctl -u mnvpn-bot.service -f  # Лив логов
```

### Шаг 4: Запуск webhook сервера (для платежей)

```bash
# Установить FastAPI и uvicorn
source .venv/bin/activate
pip install fastapi uvicorn

# Запустить webhook
python3 webhook_server.py  # Будет слушать на localhost:8000
```

### Шаг 5: Nginx reverse proxy (для вебхуков)

```bash
apt install -y nginx

cat > /etc/nginx/sites-available/mnvpn << 'EOF'
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

    location / {
        return 404;
    }
}
EOF

# Включить сайт
ln -s /etc/nginx/sites-available/mnvpn /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Шаг 6: Let's Encrypt SSL (для HTTPS)

```bash
apt install -y certbot python3-certbot-nginx

certbot certonly -d your-domain.com --standalone

# Добавить в Nginx конфиг
# listen 443 ssl http2;
# ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
# ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
```

### Шаг 7: Запуск cleanup скриптов через cron

```bash
# Отредактировать crontab
crontab -e

# Добавить строки:
0 2 * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 cleanup_subscriptions.py >> /var/log/mnvpn_cleanup.log 2>&1
0 */6 * * * cd /opt/mnvpn && /opt/mnvpn/.venv/bin/python3 check_payment_status.py >> /var/log/mnvpn_payment_check.log 2>&1
```

---

## Тестирование полного цикла

### Тестовый аккаунт в Yandex.Kassa:

```python
# Использовать тестовые карты:
# 4111 1111 1111 1111 (успешный платеж)
# 4000 0000 0000 0002 (отклоненный платеж)
```

### Проверка бота:

```
1. /start - должен показать меню
2. 💳 Купить подписку - создать счет
3. Оплатить (тестовой картой) - активировать подписку
4. 🔑 Получить VPN ключ - получить конфиг
5. 👤 Мой профиль - проверить данные
```

---

## Масштабирование (несколько серверов)

### Архитектура с балансировкой:

```
Telegram Bot (основной сервер)
    ↓
Database (PostgreSQL на отдельном VPS или облаке)
    ↓
    ├─→ VPN Server 1 (3X-UI)
    ├─→ VPN Server 2 (3X-UI)
    └─→ VPN Server 3 (3X-UI)
```

### Шаг 1: Переход на PostgreSQL

```bash
# На отдельном VPS (облачная БД)
apt install -y postgresql postgresql-contrib

# Создать базу данных
sudo -u postgres psql << EOF
CREATE USER mnvpn WITH PASSWORD 'strong_password';
CREATE DATABASE mnvpn OWNER mnvpn;
GRANT ALL PRIVILEGES ON DATABASE mnvpn TO mnvpn;
EOF

# Обновить database.py для использования PostgreSQL:
# pip install psycopg2-binary
# Заменить aiosqlite на asyncpg
```

### Шаг 2: Распределение пользователей между серверами

```python
# В vpn_service.py добавить логику выбора сервера:

async def select_vpn_server(user_id: int):
    """Select best VPN server based on load."""
    servers = [
        {"ip": "1.2.3.4", "port": 2053, "inbound_id": 1},
        {"ip": "5.6.7.8", "port": 2053, "inbound_id": 1},
        {"ip": "9.10.11.12", "port": 2053, "inbound_id": 1},
    ]
    
    # Простое распределение по user_id
    server_index = user_id % len(servers)
    return servers[server_index]
```

### Шаг 3: CDN для вебхуков

```bash
# Использовать Cloudflare для ускорения вебхуков
# https://www.cloudflare.com
```

---

## Мониторинг и логирование

### Установка Prometheus + Grafana:

```bash
# Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
```

### Логирование в ELK стек:

```bash
# В production используйте:
# - Filebeat для сбора логов
# - Elasticsearch для хранения
# - Kibana для визуализации
```

---

## Безопасность

### Важные меры безопасности:

```bash
# 1. Использовать SSH ключи (не пароли)
# 2. Disabled root login
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# 3. Включить fail2ban
apt install -y fail2ban
systemctl enable fail2ban

# 4. Регулярные бэкапы БД
0 3 * * * pg_dump mnvpn | gzip > /backup/mnvpn_$(date +\%Y\%m\%d).sql.gz

# 5. Шифрование .env файла
openssl enc -aes-256-cbc -in .env -out .env.enc

# 6. Rate limiting на вебхуки
# Добавить в webhook_server.py
```

---

## Команды для управления

```bash
# Проверить статус бота
systemctl status mnvpn-bot.service

# Посмотреть логи
journalctl -u mnvpn-bot.service -n 100 -f

# Перезагрузить бота
systemctl restart mnvpn-bot.service

# Остановить сервис
systemctl stop mnvpn-bot.service

# Проверить базу данных
sqlite3 /opt/mnvpn/db.sqlite3
> SELECT COUNT(*) FROM users;
> SELECT * FROM payments ORDER BY created_at DESC LIMIT 10;
```

---

## Решение проблем

### Бот не подключается к 3X-UI
```bash
# Проверить доступность панели
curl -k https://YOUR_SERVER_IP:2053/api/login -d "username=admin&password=..."

# Проверить firewall
ufw status
```

### Платежи не обрабатываются
```bash
# Проверить вебхук
tail -f /var/log/nginx/access.log | grep webhook

# Проверить логи webhook сервера
journalctl -u mnvpn-webhook.service -f
```

### Медленное подключение к VPN
```bash
# Проверить нагрузку сервера
htop

# Проверить пропускную способность сети
iperf3 -s  # На сервере
iperf3 -c SERVER_IP  # На клиенте
```

---

## Примерный бюджет для MVP (на год)

| Статья | Стоимость |
|--------|-----------|
| VPS сервер (2 vCore, $10/мес) | $120 |
| Домен (.com) | $12 |
| SSL сертификат | $0 (Let's Encrypt) |
| Телефон для СМС (опционально) | $0-100 |
| **Итого** | **~$150** |

**Доход при 50+ активных пользователей:**
- 50 × 100₽ = 5,000₽/месяц ≈ $60/месяц = $720/год
- Прибыль: $720 - $150 = **$570 в год** на MVP

---

## Следующие шаги

1. ✅ Развернуть MVP с одним сервером
2. 📈 Набрать первых 100 пользователей
3. 📊 Добавить аналитику и статистику
4. 🚀 Масштабировать на несколько серверов
5. 💎 Добавить премиум планы и опции
6. 🌍 Локализация на другие языки

---

**Автор:** MNVPN Team  
**Обновлено:** 2026-04-16  
**Лицензия:** MIT
