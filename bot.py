"""
MNVPN Bot — Entry point.
Initializes DB, payment service, VPN panel connection.
Runs background tasks for subscription expiry and notifications.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    BOT_TOKEN, YANDEX_KASSA_SHOP_ID, YANDEX_KASSA_API_KEY,
    YANDEX_KASSA_WEBHOOK_SECRET, REFERRAL_BONUS_DAYS
)
from database import (
    init_db, get_expired_users, get_expiring_users,
    update_user_subscription, get_user, apply_referral_bonus,
    extend_subscription, is_sub_active_str, get_user_clients
)
from handlers import router
from admin_handlers import admin_router
from vpn_service import vpn_service
from payment_service import init_payment_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

bot_instance: Bot = None


async def check_expired_subscriptions():
    """
    Background task: disable ALL devices of expired users in 3X-UI every hour.
    
    This ensures:
    1. Users with expired subscription cannot use VPN on ANY device
    2. Keys can be reactivated after payment (not deleted, just disabled)
    3. Database stays in sync with 3X-UI panel state
    """
    while True:
        try:
            expired = await get_expired_users()
            for user in expired:
                user_id = user['user_id']
                
                # Get ALL devices (clients) for this user
                devices = await get_user_clients(user_id)
                
                if not devices:
                    logger.info(f"User {user_id} has expired subscription but no devices")
                    continue
                
                # Disable EVERY device in 3X-UI
                disabled_count = 0
                for device in devices:
                    uuid = device.get('uuid')
                    device_name = device.get('device_name', 'Unknown')
                    
                    if uuid:
                        disabled = await vpn_service.disable_client(uuid)
                        if disabled:
                            disabled_count += 1
                            logger.info(
                                f"✅ Disabled device '{device_name}' (UUID: {uuid}) "
                                f"for expired user {user_id}"
                            )
                        else:
                            logger.warning(
                                f"⚠️ Failed to disable device '{device_name}' (UUID: {uuid}) "
                                f"for user {user_id}"
                            )
                
                logger.info(
                    f"User {user_id}: disabled {disabled_count}/{len(devices)} devices due to expired subscription"
                )
                
        except Exception as e:
            logger.error(f"Error checking expired subscriptions: {e}", exc_info=True)

        await asyncio.sleep(3600)  # Check every hour


async def notify_expiring_subscriptions(bot: Bot):
    """Background task: notify users 3 days before expiry."""
    while True:
        try:
            expiring = await get_expiring_users(days_before=3)
            for user in expiring:
                user_id = user['user_id']
                try:
                    expiry = user['subscription_expiry'][:10]
                    await bot.send_message(
                        user_id,
                        f"⚠️ <b>Подписка заканчивается!</b>\n\n"
                        f"📅 Дата окончания: <code>{expiry}</code>\n\n"
                        f"Продлите подписку, чтобы не потерять доступ.\n"
                        f"Нажмите /start → Управление VPN → Продлить",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass  # User may have blocked the bot
        except Exception as e:
            logger.error(f"Error sending expiry notifications: {e}")

        await asyncio.sleep(86400)  # Once per day


async def main():
    logger.info("Starting MNVPN Bot...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize payment service
    if YANDEX_KASSA_SHOP_ID and YANDEX_KASSA_API_KEY and YANDEX_KASSA_WEBHOOK_SECRET:
        init_payment_service(
            shop_id=YANDEX_KASSA_SHOP_ID,
            api_key=YANDEX_KASSA_API_KEY,
            webhook_secret=YANDEX_KASSA_WEBHOOK_SECRET
        )
        logger.info("Payment service initialized (YooKassa)")
    else:
        logger.warning("Payment service credentials not configured")

    # Connect to VPN panel
    try:
        connected = await vpn_service.login_3xui()
        if connected:
            logger.info("Connected to 3X-UI panel")
        else:
            logger.warning("Failed to connect to 3X-UI, will retry in background")
    except Exception as e:
        logger.error(f"Error connecting to VPN panel: {e}")

    # Create bot
    bot = Bot(token=BOT_TOKEN)
    global bot_instance
    bot_instance = bot

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    dp.include_router(admin_router)

    # Start background tasks
    asyncio.create_task(check_expired_subscriptions())
    asyncio.create_task(notify_expiring_subscriptions(bot))
    logger.info("Background tasks started")

    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if vpn_service.session:
            await vpn_service.session.close()


if __name__ == "__main__":
    asyncio.run(main())
