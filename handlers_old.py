from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime, timedelta
from database import add_user, get_user, update_user_subscription, update_user_device_limit, update_user_xui_data
from vpn_service import vpn_service
from config import PAYMENT_PROVIDER_TOKEN

router = Router()


def get_main_keyboard(is_active: bool = False):
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.button(text="🔑 Получить VPN ключ", callback_data="get_key")
        builder.button(text="➕ Добавить устройство (100₽)", callback_data="upgrade")
    else:
        builder.button(text="💳 Купить подписку (100₽)", callback_data="buy")
    
    builder.button(text="👤 Мой профиль", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()

def is_sub_active(expiry_str: str) -> bool:
    if not expiry_str:
        return False
    try:
        expiry = datetime.fromisoformat(expiry_str)
        return expiry > datetime.now()
    except:
        return False


@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    await add_user(user_id, username)
    
    user = await get_user(user_id)
    active = is_sub_active(user[4])

    await message.answer(
        "👋 *Добро пожаловать! [VER-1.1]*\n\n"
        "Для доступа к высокоскоростному VPN необходимо приобрести подписку.\n\n"
        "💰 *Стоимость:* 100 руб / месяц\n"
        "📱 *Лимит:* 1 устройство одновременно (можно докупить дополнительные)\n\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=get_main_keyboard(active),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "profile")
async def process_profile(callback: CallbackQuery):
    await callback.answer()
    user = await get_user(callback.from_user.id)
    if user:
        active = is_sub_active(user[4])
        status = "✅ Активна" if active else "❌ Истекла / Нет"
        expiry = user[4] if user[4] else "—"
        limit = user[5]
        
        text = (
            f"👤 *Ваш профиль*\n\n"
            f"🆔 ID: `{user[0]}`\n"
            f"🌐 Статус: {status}\n"
            f"📅 Истекает: `{expiry}`\n"
            f"📱 Лимит устройств: `{limit}`"
        )
    else:
        text = "Профиль не найден. Нажмите /start"

    await callback.message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data.in_(["buy", "upgrade"]))
async def process_payment(callback: CallbackQuery):
    await callback.answer()
    action = callback.data
    user_id = callback.from_user.id
    username = callback.from_user.username or str(user_id)
    
    # --- STUB LOGIC (SIMULATED PAYMENT) ---
    user = await get_user(user_id)
    
    if action == "buy":
        new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
        await update_user_subscription(user_id, new_expiry)
        await callback.message.answer("💳 [ЗАГЛУШКА] Оплата 100₽ имитирована успешно!\nПодписка активирована на 30 дней.")
    elif action == "upgrade":
        new_limit = (user[5] or 1) + 1
        await update_user_device_limit(user_id, new_limit)
        await callback.message.answer(f"💳 [ЗАГЛУШКА] Лимит устройств имитирован успешно!\nНовый лимит: {new_limit}")
        # Update 3X-UI if exists
        if user[6]: # uuid index
             await vpn_service.add_or_update_client(user_id, username, new_limit, client_uuid=user[6], sub_id=user[7])

    await callback.message.answer("Теперь вы можете воспользоваться VPN!", reply_markup=get_main_keyboard(True))
    # --- END STUB ---

@router.pre_checkout_query()
async def process_pre_checkout(query: CallbackQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    user_id = message.from_user.id
    payload = message.successful_payment.invoice_payload
    
    user = await get_user(user_id)
    
    if payload == "sub_buy":
        new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
        await update_user_subscription(user_id, new_expiry)
        await message.answer("✅ Оплата прошла успешно! Подписка активирована на 30 дней.")
    elif payload == "sub_upgrade":
        new_limit = (user[5] or 1) + 1
        await update_user_device_limit(user_id, new_limit)
        await message.answer(f"✅ Лимит устройств успешно увеличен до {new_limit}!")
        # If user already has a 3X-UI client, update it in the panel
        if user[6]: # uuid
            await vpn_service.add_or_update_client(user_id, message.from_user.username or str(user_id), new_limit, client_uuid=user[6], sub_id=user[7])

    await message.answer("Теперь вы можете получить свой ключ!", reply_markup=get_main_keyboard(True))

@router.callback_query(F.data == "get_key")
async def process_get_key(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not is_sub_active(user[4]):
        await callback.message.answer("❌ Ваша подписка истекла или не активна. Пожалуйста, оплатите доступ.")
        return

    # Check if client already exists in 3X-UI
    if user[6]: # uuid
        sub_id = user[7] # sub_id column
    else:
        msg = await callback.message.answer("⏳ Генерирую ваш персональный доступ...")
        username = callback.from_user.username or str(user_id)
        xui_data = await vpn_service.add_or_update_client(user_id, username, user[5], client_uuid=user[6], sub_id=user[7])
        await msg.delete()
        
        if xui_data:
            await update_user_xui_data(user_id, xui_data["uuid"], xui_data["sub_id"])
            sub_id = xui_data["sub_id"]
        else:
            await callback.message.answer("❌ Ошибка при создании доступа. Попробуйте позже.")
            return

    username = callback.from_user.username or str(user_id)
    uri = vpn_service.generate_wrapped_link(sub_id, f"Mnvpn_{username}")

    text = (
        "✅ <b>Ваш доступ готов!</b>\n\n"
        "🔗 <b>Ссылка для импорта (нажмите):</b>\n"
        f"{uri}\n\n"
        "📲 <b>Инструкция для Happ:</b>\n"
        "1️⃣ Нажмите на ссылку выше\n"
        "2️⃣ В открывшемся окне разрешите открытие приложения <b>Happ</b>\n"
        "3️⃣ Happ автоматически добавит подписку.\n\n"
        f"⚠️ <b>Лимит устройств:</b> {user[5]}"
    )

    await callback.message.answer(text, parse_mode="HTML")
