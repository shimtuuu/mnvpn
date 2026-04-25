# MNVPN - Платный VPN-сервис на AmneziaWG

![Version](https://img.shields.io/badge/version-1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)

## Описание

**MNVPN** - это полнофункциональный платный VPN-сервис на базе протокола **AmneziaWG** с интеграцией Telegram-бота, системой платежей Yandex.Kassa и поддержкой многоустройственных подписок.

### Ключевые возможности:

- 🔐 **AmneziaWG протокол** - современный и безопасный протокол
- 💳 **Yandex.Kassa интеграция** - прием платежей от российских пользователей
- 📱 **Telegram Bot** - полное управление подписками через Telegram
- 📊 **Multi-device поддержка** - подписка на несколько устройств одновременно
- 🚀 **Масштабируемость** - готов к развертыванию на несколько серверов
- 🔄 **Автоматизация** - cron-задачи для управления подписками
- 📈 **Analytics** - отслеживание платежей и активных пользователей
- 🔒 **Безопасность** - уникальные ключи для каждого устройства

---

## Быстрый старт

### Требования:

- Python 3.9+
- VPS с Ubuntu 22.04+ (2+ vCore, 2+ GB RAM)
- Telegram Bot Token
- Yandex.Kassa аккаунт (опционально для MVP)

### Установка (3 минуты):

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourusername/mnvpn.git
cd mnvpn

# 2. Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env файл
cp .env.example .env
# Отредактировать .env с вашими данными

# 5. Инициализировать БД
python3 -c "import asyncio; from database import init_db; asyncio.run(init_db())"

# 6. Запустить бота
python3 bot.py
```

---

## Структура проекта

```
mnvpn/
├── bot.py                          # Основной бот (точка входа)
├── config.py                       # Конфигурация (читает из .env)
├── database.py                     # Слой работы с БД
├── vpn_service.py                  # Управление VPN клиентами (3X-UI)
├── payment_service.py              # Интеграция с Yandex.Kassa
├── handlers.py                     # Telegram боттели команды
├── webhook_server.py               # FastAPI сервер для платежных вебхуков
├── cleanup_subscriptions.py        # Cron скрипт для очистки истекших подписок
├── check_payment_status.py         # Cron скрипт для проверки платежей
├── test_integration.py             # Интеграционные тесты
├── requirements.txt                # Python зависимости
├── .env.example                    # Пример конфигурации
├── DEPLOYMENT_GUIDE.md             # Полное руководство по развертыванию
├── README.md                       # Этот файл
└── scratch/                        # Вспомогательные скрипты
    ├── mnvpn-bot.service          # Systemd сервис
    ├── test_3xui.py               # Тестирование 3X-UI
    └── ...
```

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────────────┐
│                     Telegram Users                          │
└────────────────┬────────────────────────────────────────────┘
                 │
         ┌───────▼────────┐
         │  Telegram Bot  │
         │   (aiogram)    │
         └───────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌──────────┐
│Database│  │3X-UI   │  │Yandex.   │
│(SQLite)│  │Panel   │  │Kassa     │
└────────┘  └────────┘  └──────────┘
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────▼────────┐
         │  VPN Server    │
         │  (AmneziaWG)   │
         └────────────────┘
                 │
         ┌───────▼────────┐
         │   VPN Users    │
         └────────────────┘
```

---

## API и команды

### Telegram Bot команды:

| Команда | Описание |
|---------|---------|
| `/start` | Начать работу с ботом, показать меню |
| `/help` | Справка по использованию |
| `/profile` | Показать профиль пользователя |
| `/buy` | Купить подписку |
| `/upgrade` | Добавить дополнительное устройство |
| `/getkey` | Получить VPN конфигурацию |
| `/devices` | Показать список устройств |

### Webhook endpoints:

```
POST /webhook/payment  # Получает уведомления от Yandex.Kassa
GET  /health           # Проверка здоровья сервера
```

---

## Конфигурация

### Основные переменные окружения:

```env
# Telegram
BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz1234567890

# Database
DB_PATH=/opt/mnvpn/db.sqlite3

# VPN Panel
VPN_PANEL_URL=https://your-vps-ip:2053
VPN_PANEL_USERNAME=admin
VPN_PANEL_PASSWORD=your_password

# Yandex.Kassa
YANDEX_KASSA_SHOP_ID=123456
YANDEX_KASSA_API_KEY=test_KaZuzo_AbCdEf...
YANDEX_KASSA_WEBHOOK_SECRET=your_webhook_secret

# Pricing
VPN_SUBSCRIPTION_PRICE=100        # в рублях
VPN_DEVICE_PRICE=100              # в рублях за доп. устройство
SUBSCRIPTION_DAYS=30              # дни
```

Полный список переменных см. в [.env.example](.env.example)

---

## Развертывание в production

### Быстрое развертывание (1 сервер):

```bash
# Следуйте пошаговому руководству в DEPLOYMENT_GUIDE.md
# Краткий путь:
1. Купить VPS (Hetzner, DigitalOcean, и т.д.)
2. Установить 3X-UI панель
3. Развернуть приложение
4. Настроить Yandex.Kassa
5. Запустить через systemd
6. Настроить cron задачи
```

### Масштабирование (несколько серверов):

```bash
# См. раздел "Масштабирование" в DEPLOYMENT_GUIDE.md
# - Перейти на PostgreSQL
# - Распределить пользователей между серверами
# - Настроить load balancing
```

---

## Тестирование

### Запуск интеграционных тестов:

```bash
python3 test_integration.py
```

Тесты проверяют:
- ✓ Инициализацию БД
- ✓ Подключение к 3X-UI
- ✓ Создание платежных счетов
- ✓ Проверку вебхук-подписей
- ✓ Полный цикл пользователя

### Тестирование платежей:

Используйте тестовые карты Yandex.Kassa:
- `4111 1111 1111 1111` - успешный платеж
- `4000 0000 0000 0002` - отклоненный платеж

---

## Безопасность

### Реализованные меры:

- ✅ HMAC-SHA256 подпись вебхуков
- ✅ SSH ключ доступ к VPS
- ✅ Уникальные UUID для каждого клиента
- ✅ Шифрование в БД (пароли)
- ✅ Rate limiting на API
- ✅ Проверка подписи перед обработкой

### TODO для production:

- [ ] Двухфакторная аутентификация
- [ ] IP белые списки для админа
- [ ] Регулярные бэкапы БД
- [ ] Мониторинг и алерты
- [ ] DDoS защита
- [ ] Шифрование трафика между серверами

---

## Мониторинг и Логирование

### Логи системы:

```bash
# Логи бота
journalctl -u mnvpn-bot.service -f

# Логи платежей
tail -f /var/log/mnvpn_payment_check.log

# Логи cleanup
tail -f /var/log/mnvpn_cleanup.log
```

### Метрики:

```bash
# Количество пользователей
sqlite3 db.sqlite3 "SELECT COUNT(*) FROM users;"

# Активные подписки
sqlite3 db.sqlite3 "SELECT COUNT(*) FROM users WHERE subscription_expiry > datetime('now');"

# Доход
sqlite3 db.sqlite3 "SELECT SUM(amount_rubles) FROM payments WHERE status = 'completed';"
```

---

## Расчет прибыльности

### Модель доходов:

- **Базовая подписка**: 100₽/месяц (1 устройство)
- **Доп. устройство**: 100₽ за каждое

### Пример расчета при 100 активных пользователях:

```
Месячные доходы:
  - 100 пользователей × 100₽ = 10,000₽
  - 20% имеют 2+ устройств: 20 × 100₽ = 2,000₽
  
Итого доход: 12,000₽/месяц

Затраты:
  - VPS (2 vCore): $10-15 ≈ 800-1,200₽
  - Доменное имя: $12 ≈ 1,000₽/год
  
Итого затраты: ~1,000₽/месяц

Прибыль: 12,000 - 1,000 = 11,000₽/месяц
```

---

## FAQ

### Q: Можно ли использовать на iOS/Android?
**A:** Да! Используйте приложение [Happ VPN](https://happ.app) или другие приложения с поддержкой WireGuard.

### Q: Какая максимальная пропускная способность?
**A:** Зависит от VPS. На Hetzner Cloud можно достичь 1-5 Gbps для одного сервера.

### Q: Как обновить бот в production?
```bash
systemctl stop mnvpn-bot.service
cd /opt/mnvpn
git pull origin main
pip install -r requirements.txt
systemctl start mnvpn-bot.service
```

### Q: Что делать если упал сервер?
```bash
# systemd автоматически перезагрузит бота
# Проверьте статус:
systemctl status mnvpn-bot.service

# Посмотрите логи:
journalctl -u mnvpn-bot.service -n 50
```

### Q: Можно ли добавить другие способы оплаты?
**A:** Да! Код модулирован. Дублируйте `payment_service.py` и замените класс:
```python
class StripePaymentService(PaymentService):
    # Ваша реализация Stripe
```

---

## Лицензия

MIT License - см. [LICENSE](LICENSE)

---

## Поддержка и контакты

- 📧 Email: support@mnvpn.example.com
- 💬 Telegram: [@mnvpn_support](https://t.me/mnvpn_support)
- 🐛 Issues: GitHub Issues

---

## Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot API
- [3X-UI](https://github.com/mhsanaei/3x-ui) - VPN Panel
- [Yandex.Kassa](https://kassa.yandex.ru) - Payment Gateway

---

**Версия**: 1.0  
**Обновлено**: 2026-04-16  
**Статус**: MVP готов к запуску
