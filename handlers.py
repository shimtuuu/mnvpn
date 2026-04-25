"""
MNVPN Bot Handlers — Commercial-grade Telegram VPN bot.
Sections: Start, Manage VPN, Connect Device, My Configs, Free Trial,
Gift VPN, Referral Program, Support, Info.
"""

import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile, FSInputFile,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from aiogram.filters import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

from database import (
    add_user, get_user, update_user_subscription, extend_subscription,
    update_user_xui_data, get_user_devices, count_user_devices,
    has_used_trial, mark_trial_used, create_gift, get_gift_by_code,
    redeem_gift, add_referral, apply_referral_bonus, get_referral_stats,
    get_user_referral_code, is_sub_active_str, deactivate_device,
    record_subscription_history
)
from vpn_service import vpn_service
from payment_service import get_payment_service
from config import (
    VPN_SUBSCRIPTION_PRICE, VPN_DEVICE_PRICE, SUBSCRIPTION_DAYS,
    GIFT_PRICES, TRIAL_ENABLED, TRIAL_HOURS, REFERRAL_BONUS_DAYS,
    SUPPORT_USERNAME, BANNER_PATH, CRYPTO_WALLET_USDT,
    BRAND_NAME, BRAND_TAGLINE, PRICE_PER_DEVICE_DISPLAY, TRIAL_DAYS
)

logger = logging.getLogger(__name__)
router = Router()


# ==================== Keyboards ====================

def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu with 6 sections."""
    buttons = [
        [InlineKeyboardButton(text="🔐 Управление VPN", callback_data="manage_vpn")],
        [InlineKeyboardButton(text="🎁 Подарить VPN", callback_data="gift_menu")],
        [InlineKeyboardButton(text="🆓 Попробовать бесплатно", callback_data="free_trial")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [
            InlineKeyboardButton(text="💬 Поддержка", callback_data="support"),
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")]
    ])


def manage_vpn_kb(is_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_active:
        buttons.append([InlineKeyboardButton(text="📲 Подключить устройство", callback_data="connect_device")])
        buttons.append([InlineKeyboardButton(text="📄 Мои конфиги", callback_data="my_configs")])
        buttons.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_sub")])
    else:
        buttons.append([InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_sub")])
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================== /start ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start with optional deep-link parameters (ref_, gift_)."""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"

    # Parse deep link args
    args = message.text.split(maxsplit=1)
    deep_link = args[1] if len(args) > 1 else None

    referred_by = None
    gift_code = None

    if deep_link:
        if deep_link.startswith("ref_"):
            try:
                referred_by = int(deep_link[4:])
                if referred_by == user_id:
                    referred_by = None  # Can't refer yourself
            except ValueError:
                pass
        elif deep_link.startswith("gift_"):
            gift_code = deep_link[5:]

    # Register user
    await add_user(user_id, username, referred_by=referred_by)

    # Process referral
    if referred_by:
        user = await get_user(user_id)
        if user and user.get('referred_by') == referred_by:
            await add_referral(referred_by, user_id)

    # Process gift
    if gift_code:
        await _process_gift_redeem(message, gift_code)
        return

    # Send banner + welcome
    await _send_welcome(message)


async def _send_welcome(message: Message):
    """Send welcome banner and main menu."""
    # Removed photo to enable seamless edit_text navigation (App-like UX)
    text = (
        f"✨ <b>Добро пожаловать в {BRAND_NAME}!</b>\n\n"
        f"🚀 {BRAND_TAGLINE}.\n"
        f"💸 Тариф: <b>{PRICE_PER_DEVICE_DISPLAY}</b>.\n"
        f"🎁 Пробный период — {TRIAL_DAYS} дней. Реферальный бонус — {REFERRAL_BONUS_DAYS} дней.\n\n"
        "⬇️ <b>Выберите раздел в меню ниже:</b>"
    )
    
    # Try to edit, if it fails, send a new message
    try:
        await message.edit_text(text, reply_markup=main_menu_kb(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=main_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    await _send_welcome(callback.message)


# ==================== 🔐 Управление VPN ====================

@router.callback_query(F.data == "manage_vpn")
async def manage_vpn(callback: CallbackQuery):
    await callback.answer()
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Нажмите /start для регистрации.")
        return

    active = is_sub_active_str(user.get('subscription_expiry'))
    device_count = await count_user_devices(callback.from_user.id)

    if active:
        expiry = user['subscription_expiry'][:10]
        try:
            days_left = (datetime.fromisoformat(user['subscription_expiry']) - datetime.now()).days
        except:
            days_left = 0
        status_emoji = "🟢"
        status_text = "Активна"
    else:
        expiry = "—"
        days_left = 0
        status_emoji = "🔴"
        status_text = "Не активна"

    text = (
        f"🔐 <b>Управление VPN</b>\n\n"
        f"{status_emoji} Статус: <b>{status_text}</b>\n"
        f"📅 Действует до: <code>{expiry}</code>\n"
    )
    traffic_text = ""
    if active:
        devices = await get_user_devices(callback.from_user.id)
        total_up = 0
        total_down = 0
        for d in devices:
            if d.get('sub_id'):
                traffic = await vpn_service.get_client_traffic(d['sub_id'])
                if traffic:
                    total_up += traffic['up']
                    total_down += traffic['down']
        total_gb = (total_up + total_down) / (1024**3)
        traffic_text = f"📊 Использовано: <b>{total_gb:.2f} ГБ</b>\n"
        text += f"⏳ Осталось дней: <b>{days_left}</b>\n{traffic_text}"
    text += (
        f"📱 Устройств: <b>{device_count} / {user.get('device_limit', 1)}</b>\n\n"
        f"💰 Стоимость: <b>{int(VPN_SUBSCRIPTION_PRICE)}₽ / {SUBSCRIPTION_DAYS} дней</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=manage_vpn_kb(active),
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=manage_vpn_kb(active),
            parse_mode="HTML"
        )


# ==================== 📲 Подключить устройство ====================

@router.callback_query(F.data == "connect_device")
async def connect_device(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await get_user(user_id)

    if not user or not is_sub_active_str(user.get('subscription_expiry')):
        await callback.message.answer(
            "❌ Ваша подписка не активна.\nСначала купите или продлите подписку.",
            reply_markup=back_to_menu_kb()
        )
        return

    # Check device limit
    device_count = await count_user_devices(user_id)
    if device_count >= user.get('device_limit', 1):
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Добавить слот", callback_data="buy_device_slot")
        builder.button(text="⬅️ Назад", callback_data="manage_vpn")
        builder.adjust(1)
        await callback.message.answer(
            f"⚠️ Достигнут лимит устройств ({device_count}/{user['device_limit']}).\n"
            f"Купите дополнительный слот за {int(VPN_DEVICE_PRICE)}₽.",
            reply_markup=builder.as_markup()
        )
        return

    try:
        await callback.message.edit_text("⏳ Генерирую конфигурацию...")
    except Exception:
        pass

    try:
        username = callback.from_user.username or str(user_id)
        # Генерируем уникальное имя для устройства (Ultima Style)
        next_num = device_count + 1
        unique_name = f"MNVPN #{next_num} ({username})"
        
        device_info = await vpn_service.register_device(
            user_id=user_id,
            username=username,
            device_name=unique_name,
            limit_ip=user.get('device_limit', 1)
        )

        if not device_info:
            await callback.message.edit_text("❌ Ошибка при создании конфигурации. Попробуйте позже.")
            return

        # Build keyboard - UltimaVPN Style
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ПОДКЛЮЧИТЬ (HAPP VPN)", url=device_info["happ_link"])],
            [
                InlineKeyboardButton(text="🍎 iOS", callback_data=f"setup_ios_{device_info['device_id']}"),
                InlineKeyboardButton(text="🤖 Android", callback_data=f"setup_android_{device_info['device_id']}"),
            ],
            [
                InlineKeyboardButton(text="💻 Windows", callback_data=f"setup_pc_{device_info['device_id']}"),
                InlineKeyboardButton(text="🍏 macOS", callback_data=f"setup_mac_{device_info['device_id']}"),
            ],
            [InlineKeyboardButton(text="📋 Скопировать ссылку (Sub)", callback_data=f"copy_{device_info['sub_id']}")],
            [InlineKeyboardButton(text="🔑 Скопировать ключ (VLESS)", callback_data=f"cvless_{device_info['device_id']}")],
            [InlineKeyboardButton(text="📥 Скачать .json", callback_data=f"download_{device_info['device_id']}")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
        ])

        text = (
            "✅ <b>ВАШ VPN МОДУЛЬ ГОТОВ!</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"📱 Устройство: <b>{device_info['device_name']}</b>\n"
            f"🔒 Протоколы: <b>VLESS, VMess, Trojan, Shadowsocks</b>\n"
            f"📅 Активен до: <b>{user['subscription_expiry'][:10]}</b>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "🔹 <b>Самый простой способ:</b>\n"
            "Нажмите кнопку <b>ПОДКЛЮЧИТЬ</b> выше — Happ VPN откроется и добавит настройки автоматически.\n\n"
            "🔹 <b>Для других приложений:</b>\n"
            "Выберите вашу платформу ниже для просмотра инструкции."
        )

        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating key for user {user_id}: {e}")
        try:
            await callback.message.edit_text("❌ Ошибка. Попробуйте позже.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("cvless_"))
async def copy_vless(callback: CallbackQuery):
    device_id = callback.data.split("_")[1]
    from database import get_device
    device = await get_device(device_id)
    if not device:
        await callback.answer("❌ Устройство не найдено", show_alert=True)
        return
    
    vless_link = vpn_service.generate_vless_link(device['uuid'], device['device_name'])
    await callback.answer("✅ Ключ VLESS скопирован!")
    await callback.message.answer(
        f"🔑 <b>Ваш VLESS ключ (нажмите, чтобы скопировать):</b>\n\n"
        f"<code>{vless_link}</code>\n\n"
        f"Вставьте этот текст в ваше VPN приложение через «Импорт из буфера обмена».",
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("copy_"))
async def copy_link(callback: CallbackQuery):
    sub_id = callback.data.split("_")[1]
    sub_link = vpn_service.generate_subscription_link(sub_id)
    await callback.answer("✅ Ссылка подписки скопирована!")
    await callback.message.answer(
        f"🔗 <b>Ссылка подписки:</b>\n\n"
        f"<code>{sub_link}</code>\n\n"
        f"Используйте эту ссылку в разделе «Настройки подписок» вашего приложения.\n"
        f"Она автоматически загрузит все доступные протоколы (VLESS, VMess, Trojan, Shadowsocks).",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("download_"))
async def download_config(callback: CallbackQuery):
    await callback.answer()
    device_id = callback.data[9:]
    from database import get_device
    device = await get_device(device_id)
    if not device:
        await callback.message.answer("❌ Устройство не найдено.")
        return

    config_bytes = vpn_service.generate_config_file(device['uuid'], device['sub_id'])
    config_file = BufferedInputFile(config_bytes, filename="mnvpn_config.json")
    await callback.message.answer_document(
        document=config_file,
        caption="📥 Конфигурация для ручного импорта в V2rayNG / Happ / Nekobox"
    )


# ==================== 📄 Мои конфиги ====================

@router.callback_query(F.data == "my_configs")
async def my_configs(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    devices = await get_user_devices(user_id)

    if not devices:
        try:
            await callback.message.edit_text(
                "📱 У вас нет подключённых устройств.\n\nНажмите «Подключить устройство» для создания.",
                reply_markup=back_to_menu_kb()
            )
        except Exception:
            pass
        return

    text = "📄 <b>Ваши устройства:</b>\n\n"
    buttons = []

    for i, device in enumerate(devices, 1):
        name = device.get('device_name', f"Устройство {i}")
        created = device.get('created_at', '')[:10]
        text += f"{i}. <b>{name}</b>\n   📅 Создано: {created}\n\n"
        buttons.append([
            InlineKeyboardButton(text=f"🔑 Ключ {i}", callback_data=f"showkey_{device['device_id']}"),
            InlineKeyboardButton(text=f"❌ Удалить {i}", callback_data=f"deldev_{device['device_id']}")
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_vpn")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("showkey_"))
async def show_device_key(callback: CallbackQuery):
    await callback.answer()
    device_id = callback.data[8:]
    from database import get_device
    device = await get_device(device_id)

    if not device:
        await callback.message.answer("❌ Устройство не найдено.")
        return

    sub_link = vpn_service.generate_subscription_link(device['sub_id'])
    happ_link = vpn_service.generate_happ_deeplink(device['sub_id'])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Открыть в Happ", url=happ_link)],
        [InlineKeyboardButton(text="📥 Скачать конфиг", callback_data=f"download_{device_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="my_configs")],
    ])

    try:
        await callback.message.edit_text(
            f"🔑 <b>{device.get('device_name', 'Устройство')}</b>\n\n"
            f"🔗 Ссылка подписки:\n<code>{sub_link}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 ПОДКЛЮЧИТЬ (HAPP)", url=happ_link)],
                [
                    InlineKeyboardButton(text="🍎 iOS", callback_data=f"setup_ios_{device_id}"),
                    InlineKeyboardButton(text="🤖 Android", callback_data=f"setup_android_{device_id}"),
                ],
                [InlineKeyboardButton(text="📷 Показать QR-код", callback_data=f"showqr_{device_id}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="my_configs")],
            ]),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("showqr_"))
async def show_qr_code(callback: CallbackQuery):
    await callback.answer()
    device_id = callback.data[7:]
    from database import get_device
    device = await get_device(device_id)

    if not device:
        await callback.message.answer("❌ Устройство не найдено.")
        return

    sub_link = vpn_service.generate_subscription_link(device['sub_id'])
    qr_bytes = vpn_service.generate_qr_code(sub_link)
    
    if qr_bytes:
        qr_file = BufferedInputFile(qr_bytes, filename="mnvpn_qr.png")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="delete_this_msg")]
        ])
        await callback.message.answer_photo(
            photo=qr_file,
            caption="📷 <b>QR-код подписки</b>\nСканируйте его в приложении V2RayNG / FoXray / Nekobox.",
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        await callback.message.answer("❌ Ошибка генерации QR-кода.")

@router.callback_query(F.data == "delete_this_msg")
async def delete_this_msg(callback: CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("deldev_"))
async def delete_device_confirm(callback: CallbackQuery):
    await callback.answer()
    device_id = callback.data[7:]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirmdeldev_{device_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="my_configs"),
        ]
    ])
    try:
        await callback.message.edit_text("⚠️ Вы уверены, что хотите удалить это устройство?", reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("confirmdeldev_"))
async def delete_device_exec(callback: CallbackQuery):
    await callback.answer()
    device_id = callback.data[14:]
    success = await vpn_service.remove_device(device_id)
    if success:
        await callback.message.answer("✅ Устройство удалено.", reply_markup=back_to_menu_kb())
    else:
        await callback.message.answer("❌ Ошибка при удалении.", reply_markup=back_to_menu_kb())


# ==================== 💳 Покупка / Продление ====================

@router.callback_query(F.data == "buy_sub")
@router.callback_query(F.data == "renew_sub")
async def buy_subscription(callback: CallbackQuery):
    await callback.answer()

    buttons = []

    # Card payment (Stub mode is active)
    buttons.append([InlineKeyboardButton(text="💳 Картой", callback_data="pay_card_sub")])

    # Crypto payment
    if CRYPTO_WALLET_USDT:
        buttons.append([InlineKeyboardButton(text="💎 Крипто (USDT)", callback_data="pay_crypto_sub")])

    if not buttons:
        await callback.message.answer(
            "❌ Способы оплаты не настроены. Обратитесь в поддержку.",
            reply_markup=back_to_menu_kb()
        )
        return

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_vpn")])

    await callback.message.answer(
        f"💰 <b>Подписка MNVPN</b>\n\n"
        f"📦 Период: {SUBSCRIPTION_DAYS} дней\n"
        f"💵 Стоимость: <b>{int(VPN_SUBSCRIPTION_PRICE)}₽</b>\n\n"
        f"Выберите способ оплаты:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_card_sub")
async def pay_card_subscription(callback: CallbackQuery):
    await callback.answer()
    # Заглушка: имитация успешной оплаты для теста
    user_id = callback.from_user.id
    new_expiry = await extend_subscription(user_id, 30)
    await record_subscription_history(user_id, "test_payment_active", None, new_expiry)
    
    await callback.message.answer(
        f"✅ <b>Тестовая оплата прошла успешно!</b>\n\n"
        f"💳 Режим заглушки: подписка активирована на 30 дней.\n"
        f"📅 Новая дата: <code>{new_expiry[:10]}</code>\n\n"
        f"Теперь вы можете подключить ваше первое устройство 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Подключить VPN", callback_data="connect_device")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_crypto_sub")
async def pay_crypto_subscription(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"💎 <b>Оплата криптовалютой (USDT TRC20)</b>\n\n"
        f"💵 Сумма: <b>{int(VPN_SUBSCRIPTION_PRICE)}₽</b> (~эквивалент в USDT)\n\n"
        f"📋 Адрес кошелька:\n<code>{CRYPTO_WALLET_USDT}</code>\n\n"
        f"После перевода отправьте скриншот в поддержку @{SUPPORT_USERNAME} "
        f"и укажите ваш ID: <code>{callback.from_user.id}</code>.\n\n"
        f"Подписка будет активирована в течение 15 минут.",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "buy_device_slot")
async def buy_device_slot(callback: CallbackQuery):
    await callback.answer()
    payment_service = get_payment_service()

    buttons = []
    # Card payment (Stub mode is active)
    buttons.append([InlineKeyboardButton(text="💳 Купить слот (картой)", callback_data="pay_card_device")])
    
    if CRYPTO_WALLET_USDT:
        buttons.append([InlineKeyboardButton(text="💎 Купить слот (крипто)", callback_data="pay_crypto_device")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_vpn")])

    await callback.message.answer(
        f"📱 <b>Дополнительный слот</b>\n\n"
        f"Стоимость: <b>{int(VPN_DEVICE_PRICE)}₽</b>\n"
        f"Позволит подключить ещё одно устройство.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "pay_card_device")
async def pay_card_device(callback: CallbackQuery):
    await callback.answer()
    # Заглушка: имитация покупки слота
    user_id = callback.from_user.id
    user = await get_user(user_id)
    new_limit = (user.get('device_limit', 1)) + 1
    
    from database import update_user_device_limit
    await update_user_device_limit(user_id, new_limit)
    
    await callback.message.answer(
        f"✅ <b>Тестовая оплата слота прошла успешно!</b>\n\n"
        f"📱 Ваш лимит устройств увеличен до: <b>{new_limit}</b>",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )


# ==================== 🆓 Бесплатный период ====================

@router.callback_query(F.data == "free_trial")
async def free_trial(callback: CallbackQuery):
    await callback.answer()

    if not TRIAL_ENABLED:
        await callback.message.answer(
            "🚫 Бесплатный период временно недоступен.",
            reply_markup=back_to_menu_kb()
        )
        return

    user_id = callback.from_user.id
    used = await has_used_trial(user_id)

    if used:
        await callback.message.answer(
            "⚠️ Вы уже использовали бесплатный период.\n\n"
            f"Купите полную подписку за {int(VPN_SUBSCRIPTION_PRICE)}₽ для продолжения.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_sub")],
                [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
            ])
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Активировать ({TRIAL_HOURS}ч)", callback_data="activate_trial")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_menu")],
    ])

    await callback.message.answer(
        f"🆓 <b>Бесплатный пробный период</b>\n\n"
        f"⏰ Длительность: <b>{TRIAL_HOURS} часов</b>\n"
        f"📱 Лимит: <b>1 устройство</b>\n"
        f"🔄 Доступен: <b>1 раз</b>\n\n"
        f"После активации вы сразу получите конфигурацию для подключения.",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "activate_trial")
async def activate_trial(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    used = await has_used_trial(user_id)
    if used:
        try:
            await callback.message.edit_text("⚠️ Бесплатный период уже использован.", reply_markup=back_to_menu_kb())
        except Exception:
            pass
        return

    # Activate trial subscription
    trial_expiry = (datetime.now() + timedelta(hours=TRIAL_HOURS)).isoformat()
    await update_user_subscription(user_id, trial_expiry)
    await mark_trial_used(user_id)
    await record_subscription_history(user_id, "trial_activated", None, trial_expiry)

    try:
        await callback.message.edit_text("⏳ Активация бесплатного периода...")
    except Exception:
        pass

    # Auto-generate device
    username = callback.from_user.username or str(user_id)
    unique_name = f"🆓 Trial ({username})"
    
    device_info = await vpn_service.register_device(
        user_id=user_id,
        username=username,
        device_name=unique_name,
        limit_ip=1
    )

    if device_info:
        await update_user_xui_data(user_id, device_info["uuid"], device_info["sub_id"])
        await loading_msg.delete()

        # Build keyboard - UltimaVPN Style
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ПОДКЛЮЧИТЬ (HAPP VPN)", url=device_info["happ_link"])],
            [
                InlineKeyboardButton(text="🍎 iOS", callback_data=f"setup_ios_{device_info['device_id']}"),
                InlineKeyboardButton(text="🤖 Android", callback_data=f"setup_android_{device_info['device_id']}"),
            ],
            [
                InlineKeyboardButton(text="💻 Windows", callback_data=f"setup_pc_{device_info['device_id']}"),
                InlineKeyboardButton(text="🍏 macOS", callback_data=f"setup_mac_{device_info['device_id']}"),
            ],
            [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_{device_info['sub_id']}")],
            [InlineKeyboardButton(text="🔑 Скопировать VLESS", callback_data=f"cvless_{device_info['device_id']}")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
        ])

        text = (
            "✅ <b>БЕСПЛАТНЫЙ ПЕРИОД АКТИВИРОВАН!</b>\n"
            "━━━━━━━━━━━━━━━━━\n"
            f"📱 Устройство: <b>{device_info['device_name']}</b>\n"
            f"🔒 Протоколы: <b>VLESS, VMess, Trojan, Shadowsocks</b>\n"
            f"⏰ Действует до: <b>{trial_expiry[:16].replace('T', ' ')}</b>\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "🔹 <b>Нажмите кнопку ПОДКЛЮЧИТЬ</b> выше для автоматической настройки Happ VPN.\n\n"
            "🔹 Или выберите вашу платформу для ручной настройки."
        )

        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

        if device_info.get("qr_code"):
            qr_file = BufferedInputFile(device_info["qr_code"], filename="trial_qr.png")
            await callback.message.answer_photo(
                photo=qr_file, 
                caption="📷 <b>QR-код для импорта</b>\nСканируйте его камерой вашего VPN-приложения.",
                parse_mode="HTML"
            )
    else:
        await loading_msg.edit_text("❌ Ошибка активации. Попробуйте позже.")


# ==================== 🎁 Подарить VPN ====================

@router.callback_query(F.data == "gift_menu")
async def gift_menu(callback: CallbackQuery):
    await callback.answer()

    buttons = []
    for months, price in sorted(GIFT_PRICES.items()):
        buttons.append([InlineKeyboardButton(
            text=f"🎁 {months} мес. — {price}₽",
            callback_data=f"gift_create_{months}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")])

    try:
        await callback.message.edit_text(
            "🎁 <b>Подарить VPN</b>\n\n"
            "Выберите срок подарочной подписки.\n"
            "После оплаты вы получите ссылку, которую можно отправить другу.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("gift_create_"))
async def gift_create(callback: CallbackQuery):
    await callback.answer()
    months = int(callback.data[12:])
    days = months * 30
    price = GIFT_PRICES.get(months, 100)

    # For now, create gift immediately (payment integration later)
    code = await create_gift(callback.from_user.id, days)
    bot_info = await callback.bot.get_me()
    gift_link = f"https://t.me/{bot_info.username}?start=gift_{code}"

    try:
        await callback.message.edit_text(
            f"🎁 <b>Подарочный сертификат создан!</b>\n\n"
            f"📦 Срок: <b>{months} мес. ({days} дней)</b>\n"
            f"💵 Стоимость: <b>{price}₽</b>\n\n"
            f"🔗 Ссылка для друга:\n<code>{gift_link}</code>\n\n"
            f"Отправьте эту ссылку другу — при переходе подписка активируется автоматически!",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
    except Exception:
        pass


async def _process_gift_redeem(message: Message, gift_code: str):
    """Redeem a gift code."""
    user_id = message.from_user.id
    gift = await get_gift_by_code(gift_code)

    if not gift:
        await message.answer("❌ Подарочный код не найден.", reply_markup=main_menu_kb())
        return

    if gift['status'] != 'pending':
        await message.answer("⚠️ Этот подарок уже был использован.", reply_markup=main_menu_kb())
        return

    if gift['creator_id'] == user_id:
        await message.answer("⚠️ Нельзя использовать свой собственный подарок.", reply_markup=main_menu_kb())
        return

    # Redeem
    success = await redeem_gift(gift_code, user_id)
    if success:
        new_expiry = await extend_subscription(user_id, gift['duration_days'])
        await record_subscription_history(user_id, "gift_redeemed", None, new_expiry)

        await message.answer(
            f"🎉 <b>Подарок активирован!</b>\n\n"
            f"📦 Добавлено: <b>{gift['duration_days']} дней</b>\n"
            f"📅 Подписка до: <code>{new_expiry[:10]}</code>\n\n"
            f"Нажмите «Управление VPN» для подключения.",
            reply_markup=main_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка активации подарка.", reply_markup=main_menu_kb())


# ==================== 👥 Реферальная программа ====================

@router.callback_query(F.data == "referral")
async def referral_program(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id

    ref_code = await get_user_referral_code(user_id)
    stats = await get_referral_stats(user_id)
    bot_info = await callback.bot.get_me()

    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    try:
        await callback.message.edit_text(
            f"👥 <b>Реферальная программа</b>\n\n"
            f"Приглашайте друзей и получайте <b>+{REFERRAL_BONUS_DAYS} дня</b> к подписке за каждого!\n\n"
            f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"👤 Приглашено: <b>{stats['total_invited']}</b>\n"
            f"🎁 Бонусных дней: <b>{stats['bonus_days']}</b>",
            reply_markup=back_to_menu_kb(),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ==================== 💬 Поддержка ====================

@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Как подключиться?", callback_data="setup_general")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
    ])

    try:
        await callback.message.edit_text(
            f"💬 <b>Поддержка MNVPN</b>\n\n"
            f"По любым вопросам напишите нашему оператору.\n"
            f"Обычно отвечаем в течение 30 минут.\n\n"
            f"📧 Ваш ID для обращения: <code>{callback.from_user.id}</code>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        pass


# ==================== ℹ️ Информация ====================

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Как подключиться?", callback_data="setup_general")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_menu")],
    ])

    try:
        await callback.message.edit_text(
            "ℹ️ <b>О сервисе MNVPN</b>\n\n"
            "🔒 <b>Протоколы:</b> VLESS, VMess, Trojan, Shadowsocks\n"
            "━━━━━━━━━━━━━━━━━\n"
            "✅ Полная анонимность — без логов\n"
            "✅ Обход DPI и блокировок\n"
            "✅ Маскировка под обычный HTTPS\n"
            "✅ Безлимитный трафик\n"
            "✅ Без ограничений скорости\n"
            "✅ Работает в Китае, Иране, РФ\n"
            "━━━━━━━━━━━━━━━━━\n\n"
            "📱 <b>Поддерживаемые клиенты:</b>\n"
            "• Happ VPN (iOS/Android) — рекомендуем\n"
            "• V2rayNG (Android)\n"
            "• Nekobox (Android)\n"
            "• V2rayN (Windows)\n"
            "• Streisand (iOS)\n\n"
            f"💰 <b>Цена:</b> {int(VPN_SUBSCRIPTION_PRICE)}₽ / месяц",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        pass


# ==================== /help ====================
# ==================== 🛠 Инструкции (Ultima Style) ====================

@router.callback_query(F.data.startswith("setup_"))
async def platform_setup(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    platform = parts[1]
    device_id = parts[2]
    
    sub_link = None
    if device_id != "none":
        from database import get_device
        device = await get_device(device_id)
        if device:
            sub_link = vpn_service.generate_subscription_link(device['sub_id'])
    
    guides = {
        "ios": (
            "🍎 <b>Инструкция для iOS</b>\n\n"
            "1️⃣ Установите <b>Happ VPN</b> из App Store.\n"
            "2️⃣ Нажмите большую синюю кнопку «ПОДКЛЮЧИТЬ» в предыдущем сообщении бота.\n"
            "3️⃣ Приложение откроется и спросит разрешение на добавление конфига — нажмите <b>Allow</b>.\n"
            "4️⃣ Включите VPN переключателем.\n\n"
            "💡 <i>Альтернатива:</i> Скачайте Streisand или FoXray и добавьте ссылку вручную."
        ),
        "android": (
            "🤖 <b>Инструкция для Android</b>\n\n"
            "1️⃣ Установите <b>Happ VPN</b> или <b>v2rayNG</b> из Google Play.\n"
            "2️⃣ Скопируйте ссылку подписки или нажмите кнопку импорта.\n"
            "3️⃣ В v2rayNG: Нажмите ➕ → Импорт из буфера обмена.\n"
            "4️⃣ Выберите сервер и нажмите кнопку подключения (внизу справа).\n\n"
            "💡 <i>Совет:</i> Используйте Happ VPN для максимально простой настройки."
        ),
        "pc": (
            "💻 <b>Инструкция для Windows</b>\n\n"
            "1️⃣ Скачайте <b>v2rayN</b> с GitHub.\n"
            "2️⃣ Распакуйте архив и запустите v2rayN.exe.\n"
            "3️⃣ Нажмите <b>Subscription Group</b> → <b>Server Subscription Setting</b>.\n"
            "4️⃣ Нажмите <b>Add</b>, вставьте ссылку и имя MNVPN.\n"
            "5️⃣ Нажмите <b>Update Subscription</b>.\n"
            "6️⃣ Выберите сервер и нажмите <b>Enter</b>."
        ),
        "mac": (
            "🍏 <b>Инструкция для macOS</b>\n\n"
            "1️⃣ Рекомендуем использовать <b>V2RayXS</b> или <b>FoXray</b>.\n"
            "2️⃣ Скопируйте ссылку подписки ниже.\n"
            "3️⃣ Вставьте её в настройки подписок приложения.\n"
            "4️⃣ Обновите список серверов и подключайтесь."
        )
    }

    text = guides.get(platform, "Инструкция в разработке...")
    
    buttons = []
    if sub_link:
        buttons.append([InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_{device['sub_id']}")])
    
    back_cb = f"showkey_{device_id}" if device_id != "none" else "setup_general"
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    caption = text
    if sub_link:
        caption += f"\n\n🔗 <b>Ваша ссылка:</b>\n<code>{sub_link}</code>"
    else:
        caption += "\n\n🔑 <i>Чтобы получить персональную ссылку, сначала активируйте подписку и создайте устройство в «Управление VPN».</i>"

    try:
        await callback.message.edit_text(caption, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "setup_general")
async def setup_general(callback: CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍎 iOS", callback_data="setup_ios_none"),
            InlineKeyboardButton(text="🤖 Android", callback_data="setup_android_none"),
        ],
        [
            InlineKeyboardButton(text="💻 Windows", callback_data="setup_pc_none"),
            InlineKeyboardButton(text="🍏 macOS", callback_data="setup_mac_none"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="info")],
    ])
    try:
        await callback.message.edit_text(
            "🛠 <b>Базовая настройка</b>\n\n"
            "Для подключения вам понадобится:\n"
            "1. Приложение (Happ VPN, v2rayNG и др.)\n"
            "2. Ссылка подписки (получите в «Управление VPN»)\n\n"
            "Выберите вашу платформу для подробной инструкции:",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception:
        pass

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Справка MNVPN</b>\n\n"
        "<b>Как подключить VPN?</b>\n"
        "→ Меню → Управление VPN → Подключить устройство\n\n"
        "<b>Как добавить второе устройство?</b>\n"
        "→ Купите дополнительный слот в «Управление VPN»\n\n"
        "<b>Не подключается?</b>\n"
        "→ Обновите подписку в приложении\n"
        "→ Проверьте интернет\n"
        f"→ Напишите @{SUPPORT_USERNAME}\n\n"
        "<b>Как пригласить друга?</b>\n"
        "→ Меню → Реферальная программа",
        reply_markup=back_to_menu_kb(),
        parse_mode="HTML"
    )
