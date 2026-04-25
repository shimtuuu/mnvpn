#!/usr/bin/env python3
"""
Periodic payment status check script.

This script checks pending payments in Yandex.Kassa and updates subscription statuses.
Can be run every 10-30 minutes via cron.

Handles cases where webhook delivery failed but payment was successful.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/opt/mnvpn')

from database import (
    get_user, get_user_payments, update_payment_status,
    update_user_subscription, update_user_device_limit,
    record_subscription_history
)
from payment_service import get_payment_service
from config import BOT_TOKEN, SUBSCRIPTION_DAYS
from aiogram import Bot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_pending_payments():
    """Check status of pending payments in Yandex.Kassa."""
    import aiosqlite
    from config import DB_PATH
    
    payment_service = get_payment_service()
    if not payment_service:
        logger.error("Payment service not initialized")
        return False
    
    logger.info("Checking pending payments...")
    
    bot = Bot(token=BOT_TOKEN)
    updated_count = 0
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Find pending payments
            async with db.execute('''
                SELECT payment_id, user_id, external_payment_id, amount_rubles, metadata
                FROM payments 
                WHERE status = 'pending' 
                AND created_at > datetime('now', '-7 days')
            ''') as cursor:
                pending_payments = await cursor.fetchall()
        
        logger.info(f"Found {len(pending_payments)} pending payments")
        
        for payment_id, user_id, external_payment_id, amount, metadata in pending_payments:
            try:
                if not external_payment_id:
                    logger.debug(f"Payment {payment_id} has no external ID, skipping")
                    continue
                
                # Check status in Yandex.Kassa
                status = await payment_service.check_payment_status(external_payment_id)
                
                if status == "succeeded":
                    logger.info(f"Payment {payment_id} succeeded in Kassa, updating...")
                    
                    # Parse metadata to get payment type
                    import json
                    try:
                        metadata_dict = json.loads(metadata) if isinstance(metadata, str) else {}
                    except:
                        metadata_dict = {}
                    
                    payment_type = metadata_dict.get("type", "subscription")
                    
                    # Update payment status
                    await update_payment_status(payment_id, "completed", external_payment_id)
                    
                    # Process subscription activation
                    user = await get_user(user_id)
                    if user:
                        if payment_type == "subscription":
                            old_expiry = user[2]
                            new_expiry = (datetime.now() + timedelta(days=SUBSCRIPTION_DAYS)).isoformat()
                            await update_user_subscription(user_id, new_expiry)
                            await record_subscription_history(
                                user_id=user_id,
                                action="subscription_purchased",
                                old_expiry=old_expiry,
                                new_expiry=new_expiry,
                                payment_id=payment_id
                            )
                            logger.info(f"Subscription activated for user {user_id}")
                            updated_count += 1
                        
                        elif payment_type == "device_upgrade":
                            new_limit = user[3] + 1
                            await update_user_device_limit(user_id, new_limit)
                            logger.info(f"Device limit increased for user {user_id} to {new_limit}")
                            updated_count += 1
                        
                        # Notify user
                        try:
                            message = (
                                "✅ *Ваша оплата подтверждена!*\n\n"
                                f"Сумма: {amount}₽\n"
                                "Спасибо за покупку!"
                            )
                            await bot.send_message(user_id, message, parse_mode="Markdown")
                        except Exception as e:
                            logger.warning(f"Could not notify user {user_id}: {e}")
                
                elif status == "canceled":
                    logger.info(f"Payment {payment_id} was canceled")
                    await update_payment_status(payment_id, "cancelled", external_payment_id)
                
                elif status == "pending":
                    # Still pending, check age
                    created_hours_ago = 24  # Placeholder
                    if created_hours_ago > 72:
                        # More than 3 days pending, mark as failed
                        logger.info(f"Payment {payment_id} pending for too long, marking as failed")
                        await update_payment_status(payment_id, "failed", external_payment_id)
                
            except Exception as e:
                logger.error(f"Error checking payment {payment_id}: {e}")
        
        logger.info(f"Payment status check completed: {updated_count} payments processed")
        return True
    
    finally:
        await bot.session.close()


async def resend_failed_notifications():
    """Resend payment notifications that may have failed."""
    import aiosqlite
    from config import DB_PATH
    
    logger.info("Checking for failed notifications...")
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Find recently completed payments that haven't been notified
            async with db.execute('''
                SELECT p.payment_id, p.user_id, p.amount_rubles, p.completed_at, pm.metadata
                FROM payments p
                WHERE p.status = 'completed' 
                AND p.completed_at > datetime('now', '-1 hour')
                AND NOT EXISTS (
                    SELECT 1 FROM subscription_history 
                    WHERE payment_id = p.payment_id
                )
            ''') as cursor:
                payments = await cursor.fetchall()
        
        for payment_id, user_id, amount, completed_at, metadata in payments:
            try:
                logger.info(f"Sending notification for payment {payment_id} to user {user_id}")
                
                message = (
                    "✅ *Спасибо за оплату!*\n\n"
                    f"Платеж на сумму {amount}₽ успешно обработан.\n\n"
                    "Ваша подписка активирована. "
                    "Нажмите 'Получить VPN ключ' для начала использования."
                )
                
                await bot.send_message(user_id, message, parse_mode="Markdown")
            
            except Exception as e:
                logger.warning(f"Could not notify user {user_id}: {e}")
    
    finally:
        await bot.session.close()


async def check_subscription_renewals():
    """Check if any subscriptions need automatic renewal."""
    import aiosqlite
    from config import DB_PATH
    
    logger.info("Checking for subscription renewals...")
    
    # This would integrate with Yandex.Kassa recurring payments
    # For now, just log
    logger.debug("Subscription renewal check (not yet implemented)")


async def main():
    logger.info("=== Starting Payment Status Check ===")
    
    try:
        await check_pending_payments()
        await resend_failed_notifications()
        # await check_subscription_renewals()  # Future feature
        
        logger.info("=== Payment Status Check Completed ===")
        return True
    
    except Exception as e:
        logger.error(f"Critical error during payment check: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
