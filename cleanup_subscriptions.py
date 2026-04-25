#!/usr/bin/env python3
"""
Cron job script to check and cleanup expired subscriptions.

Should be run daily via crontab:
0 2 * * * cd /path/to/mnvpn && python3 cleanup_subscriptions.py

This script:
1. Finds users with expired subscriptions
2. Removes their VPN clients from the 3X-UI panel
3. Sends reminder notifications to users with expiring subscriptions (7 days left)
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, '/path/to/mnvpn')

from database import get_user, update_user_subscription
from vpn_service import vpn_service
from config import BOT_TOKEN
from aiogram import Bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_expired_subscriptions():
    """Find and cleanup expired subscriptions."""
    import aiosqlite
    from config import DB_PATH
    
    logger.info("Starting subscription cleanup...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Find all users
        async with db.execute('SELECT user_id, subscription_expiry, uuid FROM users WHERE subscription_expiry IS NOT NULL') as cursor:
            users = await cursor.fetchall()
    
    now = datetime.now()
    expired_count = 0
    reminder_count = 0
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        for user_id, expiry_str, uuid in users:
            try:
                if not expiry_str:
                    continue
                
                expiry = datetime.fromisoformat(expiry_str)
                days_remaining = (expiry - now).days
                
                # Delete if expired (past by 1 day)
                if days_remaining < -1:
                    if uuid:
                        # Remove client from VPN panel
                        deleted = await vpn_service.delete_client(uuid)
                        if deleted:
                            logger.info(f"Removed expired client for user {user_id}")
                            expired_count += 1
                        
                        # Notify user
                        try:
                            await bot.send_message(
                                user_id,
                                "❌ *Ваша подписка истекла*\n\n"
                                "Доступ к VPN отключен.\n"
                                "Для продления подписки нажмите 'Купить подписку'.",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logger.warning(f"Could not notify user {user_id}: {e}")
                
                # Send reminder if expiring in 7 days
                elif 0 < days_remaining <= 7:
                    try:
                        await bot.send_message(
                            user_id,
                            f"⚠️ *Ваша подписка истекает!*\n\n"
                            f"Дней осталось: {days_remaining}\n"
                            f"Дата истечения: {expiry.strftime('%Y-%m-%d')}\n\n"
                            f"Продлите подписку вовремя, чтобы не потерять доступ.",
                            parse_mode="Markdown"
                        )
                        reminder_count += 1
                        logger.info(f"Sent reminder to user {user_id} (expires in {days_remaining} days)")
                    except Exception as e:
                        logger.warning(f"Could not send reminder to user {user_id}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing user {user_id}: {e}")
        
        logger.info(f"Cleanup completed: {expired_count} expired subscriptions removed, {reminder_count} reminders sent")
    
    finally:
        await bot.session.close()


async def cleanup_inactive_devices():
    """Remove devices that haven't been accessed in 90 days."""
    import aiosqlite
    from config import DB_PATH
    
    logger.info("Starting inactive device cleanup...")
    
    cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT device_id, uuid FROM devices 
            WHERE last_accessed < ? AND is_active = 1
        ''', (cutoff_date,)) as cursor:
            devices = await cursor.fetchall()
        
        deleted_count = 0
        for device_id, uuid in devices:
            try:
                deleted = await vpn_service.delete_client(uuid)
                if deleted:
                    await db.execute('UPDATE devices SET is_active = 0 WHERE device_id = ?', (device_id,))
                    await db.commit()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting device {device_id}: {e}")
        
        logger.info(f"Inactive device cleanup completed: {deleted_count} devices removed")


async def main():
    """Run all cleanup tasks."""
    logger.info("=== MNVPN Subscription Cleanup Started ===")
    
    try:
        # Reconnect to VPN panel
        connected = await vpn_service.login_3xui()
        if not connected:
            logger.error("Could not connect to VPN panel")
            return False
        
        # Run cleanup tasks
        await cleanup_expired_subscriptions()
        await cleanup_inactive_devices()
        
        logger.info("=== Cleanup Completed Successfully ===")
        return True
    
    except Exception as e:
        logger.error(f"Critical error during cleanup: {e}")
        return False
        
    finally:
        await vpn_service.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
