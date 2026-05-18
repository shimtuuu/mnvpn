"""
Database layer for MNVPN commercial bot.
SQLite with aiosqlite. Tables: users, devices, payments, subscription_history,
referrals, gifts, trials.
"""

import aiosqlite
import logging
import secrets
import string
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== Schema ====================

async def init_db():
    """Initialize database schema with all required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_expiry TEXT DEFAULT NULL,
                device_limit INTEGER DEFAULT 1,
                max_devices INTEGER DEFAULT 1,
                uuid TEXT DEFAULT NULL,
                sub_id TEXT DEFAULT NULL,
                has_key BOOLEAN DEFAULT 0,
                key_data TEXT DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                balance_rubles REAL DEFAULT 0.0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER DEFAULT NULL,
                trial_used BOOLEAN DEFAULT 0,
                max_devices INTEGER DEFAULT 1,
                is_blocked BOOLEAN DEFAULT 0
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                device_name TEXT,
                uuid TEXT UNIQUE NOT NULL,
                sub_id TEXT UNIQUE NOT NULL,
                config_format TEXT DEFAULT 'vless',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_accessed TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount_rubles REAL NOT NULL,
                payment_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                provider TEXT,
                external_payment_id TEXT UNIQUE,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                metadata TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscription_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT,
                old_expiry TEXT,
                new_expiry TEXT,
                payment_id TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(payment_id) REFERENCES payments(payment_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL UNIQUE,
                bonus_applied BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(referrer_id) REFERENCES users(user_id),
                FOREIGN KEY(referred_id) REFERENCES users(user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS gifts (
                gift_id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                recipient_id INTEGER DEFAULT NULL,
                duration_days INTEGER NOT NULL,
                gift_code TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                redeemed_at TEXT DEFAULT NULL,
                FOREIGN KEY(creator_id) REFERENCES users(user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS trials (
                user_id INTEGER PRIMARY KEY,
                activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Migration: add new columns to existing users table
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]

        migrations = {
            'created_at': "ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT ''",
            'balance_rubles': "ALTER TABLE users ADD COLUMN balance_rubles REAL DEFAULT 0.0",
            'referral_code': "ALTER TABLE users ADD COLUMN referral_code TEXT",
            'referred_by': "ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL",
            'trial_used': "ALTER TABLE users ADD COLUMN trial_used BOOLEAN DEFAULT 0",
            'max_devices': "ALTER TABLE users ADD COLUMN max_devices INTEGER DEFAULT 1",
            'is_blocked': "ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0",
            'max_devices': "ALTER TABLE users ADD COLUMN max_devices INTEGER DEFAULT 1",
        }
        for col, sql in migrations.items():
            if col not in columns:
                await db.execute(sql)

        await db.commit()
        logger.info("Database initialized with all tables.")


# ==================== User Management ====================

def _generate_referral_code() -> str:
    """Generate a short unique referral code."""
    return ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))


async def add_user(user_id: int, username: str, referred_by: int = None):
    """Add a new user or ignore if exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        ref_code = _generate_referral_code()
        await db.execute(
            '''INSERT OR IGNORE INTO users 
               (user_id, username, referral_code, referred_by) 
               VALUES (?, ?, ?, ?)''',
            (user_id, username, ref_code, referred_by)
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    """Get user as a dictionary."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_user_subscription(user_id: int, expiry_date: str):
    """Update subscription expiry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET subscription_expiry = ? WHERE user_id = ?',
            (expiry_date, user_id)
        )
        await db.commit()
        logger.info(f"User {user_id} subscription updated to {expiry_date}")


async def extend_subscription(user_id: int, days: int):
    """Extend subscription by N days from NOW (no accumulation like Ultima VPN)."""
    user = await get_user(user_id)
    if not user:
        return

    # IMPORTANT: Always start from NOW, period does NOT accumulate
    new_expiry = (datetime.now() + timedelta(days=days)).isoformat()
    await update_user_subscription(user_id, new_expiry)
    return new_expiry


async def purchase_subscription(user_id: int, devices: int, days: int):
    """Purchase subscription with device limit and period (Ultima VPN model)."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Period always starts from NOW, not accumulated
        new_expiry = (datetime.now() + timedelta(days=days)).isoformat()
        
        await db.execute(
            '''UPDATE users 
               SET subscription_expiry = ?, max_devices = ?, device_limit = ?
               WHERE user_id = ?''',
            (new_expiry, devices, devices, user_id)
        )
        await db.commit()
        logger.info(f"User {user_id} purchased {devices} devices for {days} days until {new_expiry}")
        return new_expiry


async def update_user_device_limit(user_id: int, limit: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET device_limit = ?, max_devices = ? WHERE user_id = ?',
            (limit, limit, user_id)
        )
        await db.commit()


async def get_user_clients(user_id: int) -> List[dict]:
    """Get all clients (devices) for a specific user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM devices WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_user_xui_data(user_id: int, uuid: str, sub_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET uuid = ?, sub_id = ?, has_key = 1 WHERE user_id = ?',
            (uuid, sub_id, user_id)
        )
        await db.commit()


async def block_user(user_id: int, blocked: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET is_blocked = ? WHERE user_id = ?',
            (1 if blocked else 0, user_id)
        )
        await db.commit()


async def get_all_users(limit: int = 100, offset: int = 0) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (limit, offset)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_users_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            row = await cursor.fetchone()
            return row[0]


async def get_active_subscriptions_count() -> int:
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM users WHERE subscription_expiry > ?', (now,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def get_expiring_users(days_before: int = 3) -> List[dict]:
    """Get users whose subscription expires in N days."""
    now = datetime.now()
    threshold = (now + timedelta(days=days_before)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT * FROM users 
               WHERE subscription_expiry > ? AND subscription_expiry <= ?''',
            (now.isoformat(), threshold)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_expired_users() -> List[dict]:
    """Get users with expired subscriptions who still have keys."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT * FROM users 
               WHERE subscription_expiry IS NOT NULL 
               AND subscription_expiry < ? AND has_key = 1''',
            (now,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


def is_sub_active_str(expiry_str: str) -> bool:
    """Check if subscription is still active."""
    if not expiry_str:
        return False
    try:
        return datetime.fromisoformat(expiry_str) > datetime.now()
    except:
        return False


# ==================== Device Management ====================

async def add_device(device_id: str, user_id: int, device_name: str, uuid: str, sub_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO devices (device_id, user_id, device_name, uuid, sub_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_id, user_id, device_name, uuid, sub_id))
        await db.commit()
        logger.info(f"Device {device_id} added for user {user_id}")


async def get_user_devices(user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM devices WHERE user_id = ? AND is_active = 1',
            (user_id,)
        ) as cursor:
            return [dict(r) for r in await cursor.fetchall()]


async def get_device(device_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM devices WHERE device_id = ?', (device_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def deactivate_device(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE devices SET is_active = 0 WHERE device_id = ?', (device_id,)
        )
        await db.commit()


async def count_user_devices(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM devices WHERE user_id = ? AND is_active = 1',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


# ==================== Payment Management ====================

async def add_payment(payment_id: str, user_id: int, amount_rubles: float,
                      payment_type: str, provider: str = None, description: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO payments 
            (payment_id, user_id, amount_rubles, payment_type, provider, description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        ''', (payment_id, user_id, amount_rubles, payment_type, provider, description))
        await db.commit()


async def get_payment(payment_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM payments WHERE payment_id = ?', (payment_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_payment_status(payment_id: str, status: str, external_payment_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        completed_at = datetime.now().isoformat() if status == 'completed' else None
        await db.execute('''
            UPDATE payments 
            SET status = ?, completed_at = ?, external_payment_id = ?
            WHERE payment_id = ?
        ''', (status, completed_at, external_payment_id, payment_id))
        await db.commit()


async def get_total_revenue() -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount_rubles), 0) FROM payments WHERE status = 'completed'"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0]


async def record_subscription_history(user_id: int, action: str, old_expiry: str,
                                      new_expiry: str, payment_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO subscription_history 
            (user_id, action, old_expiry, new_expiry, payment_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, action, old_expiry, new_expiry, payment_id))
        await db.commit()


# ==================== Referral System ====================

async def add_referral(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                'INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)',
                (referrer_id, referred_id)
            )
            await db.commit()
            return True
        except Exception:
            return False


async def apply_referral_bonus(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE referrals SET bonus_applied = 1 WHERE referrer_id = ? AND referred_id = ?',
            (referrer_id, referred_id)
        )
        await db.commit()


async def get_referral_stats(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,)
        ) as cursor:
            total = (await cursor.fetchone())[0]

        async with db.execute(
            'SELECT COUNT(*) FROM referrals WHERE referrer_id = ? AND bonus_applied = 1',
            (user_id,)
        ) as cursor:
            bonused = (await cursor.fetchone())[0]

    return {"total_invited": total, "bonuses_applied": bonused, "bonus_days": bonused * 3}


async def get_user_referral_code(user_id: int) -> Optional[str]:
    user = await get_user(user_id)
    return user['referral_code'] if user else None


# ==================== Gift System ====================

def _generate_gift_code() -> str:
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))


async def create_gift(creator_id: int, duration_days: int) -> str:
    code = _generate_gift_code()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT INTO gifts (creator_id, duration_days, gift_code) VALUES (?, ?, ?)''',
            (creator_id, duration_days, code)
        )
        await db.commit()
    return code


async def get_gift_by_code(code: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM gifts WHERE gift_code = ?', (code,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def redeem_gift(code: str, recipient_id: int) -> bool:
    gift = await get_gift_by_code(code)
    if not gift or gift['status'] != 'pending':
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''UPDATE gifts SET recipient_id = ?, status = 'redeemed', 
               redeemed_at = ? WHERE gift_code = ?''',
            (recipient_id, datetime.now().isoformat(), code)
        )
        await db.commit()
    return True


# ==================== Trial System ====================

async def has_used_trial(user_id: int) -> bool:
    user = await get_user(user_id)
    return bool(user and user.get('trial_used'))


async def mark_trial_used(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET trial_used = 1 WHERE user_id = ?', (user_id,))
        await db.execute(
            'INSERT OR REPLACE INTO trials (user_id, expires_at) VALUES (?, ?)',
            (user_id, (datetime.now() + timedelta(hours=24)).isoformat())
        )
        await db.commit()
