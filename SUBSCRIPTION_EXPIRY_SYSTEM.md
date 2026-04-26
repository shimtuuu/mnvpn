# Система истечения подписок MNVPN

## 📝 Обзор

Система автоматически отслеживает истечение подписок и управляет доступом к VPN на уровне 3X-UI панели.

### Основные функции

1. **Автоматическая деактивация** — при истечении подписки все устройства пользователя отключаются
2. **Автоматическая реактивация** — при продлении подписки все устройства включаются обратно
3. **Уведомления** — пользователь получает предупреждение за 3 дня до истечения
4. **Безопасное хранение** — ключи **не удаляются**, только отключаются

---

## 🔄 Жизненный цикл подписки

```
[Активная подписка]
  ↓
  subscription_expiry > NOW
  ✅ Все устройства включены (enable=true)
  ↓
  ⌛ 3 дня до истечения
  ↓
  🔔 Уведомление пользователю
  ↓
[Подписка истекла]
  ↓
  subscription_expiry < NOW
  ❌ Все устройства отключены (enable=false)
  ↓
  💳 Пользователь продлевает подписку
  ↓
  ✅ Все устройства включены автоматически
  ↓
[Активная подписка]
```

---

## 🛠️ Архитектура

### 1. Фоновые задачи (`bot.py`)

#### Задача №️1: `check_expired_subscriptions()`
- **Частота**: каждый час (3600 секунд)
- **Действия**:
  1. Находит всех пользователей с `subscription_expiry < NOW`
  2. Для каждого пользователя:
     - Получает все устройства из базы (`get_user_clients()`)
     - Вызывает `vpn_service.disable_client(uuid)` для **каждого** UUID
  3. Логирует количество отключённых устройств

```python
async def check_expired_subscriptions():
    while True:
        expired = await get_expired_users()
        for user in expired:
            user_id = user['user_id']
            devices = await get_user_clients(user_id)  # ВСЕ устройства
            
            for device in devices:
                uuid = device.get('uuid')
                if uuid:
                    await vpn_service.disable_client(uuid)  # Отключаем
        
        await asyncio.sleep(3600)  # 1 час
```

#### Задача №️2: `notify_expiring_subscriptions(bot)`
- **Частота**: один раз в сутки (86400 секунд)
- **Действия**:
  1. Находит пользователей с подпиской, истекающей через 3 дня
  2. Отправляет предупреждающее сообщение в Telegram

---

### 2. Обработка платежей (`payment_service.py`)

#### Метод: `_reactivate_all_user_devices(user_id)`

Вызывается **автоматически** при успешной оплате подписки:

```python
if payment_type == "subscription":
    # 1. Обновляем дату подписки
    new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
    await update_user_subscription(user_id, new_expiry)
    
    # 2. РЕАКТИВИРУЕМ ВСЕ УСТРОЙСТВА
    await self._reactivate_all_user_devices(user_id)
```

**Алгоритм реактивации**:
1. Получает все устройства из базы (`get_user_clients()`)
2. Для каждого UUID:
   - Вызывает `vpn_service.enable_client(uuid)`
   - Логирует результат
3. Возвращает количество реактивированных устройств

---

### 3. VPN сервис (`vpn_service.py`)

#### Метод: `enable_client(client_uuid)`
Включает клиента во **всех** inbound'ах 3X-UI:

```python
async def enable_client(self, client_uuid: str) -> bool:
    inbounds = await self.get_inbounds()
    success = False
    
    for inbound in inbounds:
        inbound_id = inbound.get("id")
        url = f"{VPN_PANEL_URL}/panel/api/inbounds/{inbound_id}/{client_uuid}/setEnable"
        payload = {"id": inbound_id, "uuid": client_uuid, "enable": True}
        
        async with session.post(url, json=payload) as resp:
            if resp.status == 200 and result.get("success"):
                success = True
    
    return success
```

#### Метод: `disable_client(client_uuid)`
Аналогично `enable_client()`, но `enable: False`.

---

## 📁 База данных

### Функции для работы с подписками (`database.py`)

#### `get_expired_users() -> List[dict]`
Возвращает пользователей с:
- `subscription_expiry < NOW`
- `has_key = 1` (есть активные ключи)

```sql
SELECT * FROM users 
WHERE subscription_expiry IS NOT NULL 
  AND subscription_expiry < ? 
  AND has_key = 1
```

#### `get_expiring_users(days_before=3) -> List[dict]`
Возвращает пользователей, у которых подписка истекает через N дней.

```sql
SELECT * FROM users 
WHERE subscription_expiry > NOW 
  AND subscription_expiry <= (NOW + INTERVAL '3 days')
```

#### `get_user_clients(user_id) -> List[dict]`
Возвращает **все** устройства пользователя:

```sql
SELECT * FROM devices WHERE user_id = ?
```

Каждое устройство содержит:
- `device_id` — внутренний ID
- `uuid` — UUID клиента в 3X-UI (используется для enable/disable)
- `sub_id` — subscription ID
- `device_name` — человекочитаемое имя
- `is_active` — статус в базе (не связан с 3X-UI)

#### `is_sub_active_str(expiry_str) -> bool`
Проверяет активность подписки:

```python
return datetime.fromisoformat(expiry_str) > datetime.now()
```

---

## 🔑 Ключевые моменты

### Почему ключи НЕ удаляются?

Ключи только **отключаются** (`enable: false`), но **не удаляются** из 3X-UI. Это позволяет:

1. **Мгновенное восстановление** — при продлении подписки ключи сразу работают
2. **Сохранение настроек** — пользователь не теряет конфигурацию
3. **История подключений** — можно отслеживать статистику

### Почему необходимо отключать ВСЕ устройства?

Пользователь может иметь несколько устройств:
- Телефон (iPhone)
- Ноутбук (MacBook)
- Роутер (домашняя сеть)

Каждое устройство — отдельный клиент в 3X-UI с уникальным UUID. Если отключить только один UUID, остальные будут работать.

---

## 🚦 Сценарии работы

### Сценарий 1: Подписка истекла

1. **23:00, 25 апреля** — подписка пользователя истекает
2. **00:00, 26 апреля** — фоновая задача `check_expired_subscriptions()` обнаруживает истекшую подписку
3. **Действия**:
   - Получает все устройства пользователя (3 UUID)
   - Отключает каждое устройство в 3X-UI
   - Лог: `User 12345: disabled 3/3 devices due to expired subscription`
4. **Результат**: Все VPN-ключи пользователя перестали работать

### Сценарий 2: Продление подписки

1. **10:00, 26 апреля** — пользователь оплачивает подписку
2. **10:01** — YooKassa отправляет webhook `payment.succeeded`
3. **Действия `payment_service.process_webhook()`**:
   - Обновляет `subscription_expiry` на +30 дней
   - Вызывает `_reactivate_all_user_devices(user_id)`
   - Получает все устройства (3 UUID)
   - Включает каждое устройство в 3X-UI
   - Лог: `User 12345: reactivated 3/3 devices after payment`
4. **Результат**: Все VPN-ключи немедленно заработали

### Сценарий 3: Предупреждение об истечении

1. **22 апреля** — подписка истекает 25 апреля (3 дня)
2. **Ежедневная задача `notify_expiring_subscriptions()`** обнаруживает пользователя
3. **Действие**: Отправляет Telegram-сообщение:

```
⚠️ Подписка заканчивается!

📅 Дата окончания: 2026-04-25

Продлите подписку, чтобы не потерять доступ.
Нажмите /start → Управление VPN → Продлить
```

---

## 🔍 Мониторинг и логирование

### Логи деактивации (`bot.py`)

```
INFO: User 12345 has expired subscription but no devices
INFO: ✅ Disabled device 'iPhone 14' (UUID: abc123...) for expired user 12345
WARNING: ⚠️ Failed to disable device 'MacBook' (UUID: def456...) for user 12345
INFO: User 12345: disabled 2/3 devices due to expired subscription
```

### Логи реактивации (`payment_service.py`)

```
INFO: ✅ Subscription activated for user 12345 until 2026-05-26T10:01:00
INFO: ✅ Reactivated device 'iPhone 14' (UUID: abc123...) for user 12345
INFO: ✅ Reactivated device 'MacBook' (UUID: def456...) for user 12345
INFO: ✅ Reactivated device 'Home Router' (UUID: ghi789...) for user 12345
INFO: 💚 User 12345: reactivated 3/3 devices after payment
INFO: 💳 Payment succeeded for user 12345: subscription extended, 3 devices reactivated
```

---

## ✅ Чек-лист работы системы

- [x] Фоновая задача `check_expired_subscriptions()` запускается каждый час
- [x] Фоновая задача `notify_expiring_subscriptions()` запускается раз в сутки
- [x] При истечении отключаются **все** устройства пользователя
- [x] При продлении включаются **все** устройства пользователя
- [x] Ключи не удаляются, только отключаются (`enable: false`)
- [x] Логирование каждого действия с указанием UUID и имени устройства
- [x] Подсчёт успешно деактивированных/реактивированных устройств
- [x] Обработка ошибок с подробным логированием

---

## 🚧 Возможные улучшения

### 1. Грациозное отключение (Grace Period)

Добавить период отсрочки (24 часа) после истечения, чтобы пользователь мог продлить подписку:

```python
def is_expired_with_grace(expiry_str: str, grace_hours: int = 24) -> bool:
    expiry = datetime.fromisoformat(expiry_str)
    grace_deadline = expiry + timedelta(hours=grace_hours)
    return datetime.now() > grace_deadline
```

### 2. Селективная реактивация

Реактивировать только устройства, которые были активны до истечения:

```python
# Добавить поле last_active_before_expiry в devices
# При деактивации сохранять текущее состояние
# При реактивации восстанавливать только ранее активные
```

### 3. Webhook для мониторинга

Отправлять уведомления в Slack/Discord при:
- Сбое деактивации устройства
- Массовом истечении подписок (>50 за час)
- Проблемах соединения с 3X-UI

### 4. Метрики

Добавить счётчики:
- `devices_disabled_count` — количество отключенных устройств за последний час
- `devices_reactivated_count` — количество реактивированных устройств
- `average_reactivation_time` — среднее время от платежа до реактивации

---

## 🐛 Отладка

### Как проверить, что система работает?

1. **Проверка логов**:
```bash
tail -f bot_debug.log | grep -E "(disabled|reactivated|expired)"
```

2. **Ручной запуск проверки**:
```python
# В Python shell
import asyncio
from database import get_expired_users
from vpn_service import vpn_service

async def test():
    expired = await get_expired_users()
    print(f"Found {len(expired)} expired users")
    for user in expired:
        print(f"User {user['user_id']}: expiry {user['subscription_expiry']}")

asyncio.run(test())
```

3. **Проверка 3X-UI**:
   - Зайти в панель 3X-UI
   - Открыть Inbound → Clients
   - Найти клиента по email
   - Проверить статус `Enable` (галочка)

---

## 📚 Ссылки

- `bot.py` — фоновые задачи
- `payment_service.py` — обработка платежей
- `vpn_service.py` — управление 3X-UI
- `database.py` — работа с базой данных
