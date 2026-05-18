"""
Admin handlers for MinVPN bot.
Inline Telegram admin panel: stats, user management, broadcast, crypto confirmation.
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from config import ADMIN_IDS, SUBSCRIPTION_DAYS, REFERRAL_BONUS_DAYS
from database import (
    get_user, get_all_users, get_users_count, get_active_subscriptions_count,
    get_total_revenue, block_user, extend_subscription, update_user_subscription,
    record_subscription_history, is_sub_active_str
)
from vpn_service import vpn_service

logger = logging.getLogger(__name__)
admin_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class BroadcastState(StatesGroup):
    waiting_message = State()


class ManageUserState(StatesGroup):
    waiting_user_id = State()
    waiting_extend_days = State()


# ==================== Admin Menu ====================

def admin_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users_0")],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📈 Онлайн сейчас", callback_data="admin_online")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return

    await message.answer(
        "⚙️ <b>Админ-панель MinVPN</b>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )


# ==================== Stats ====================

@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await callback.answer()

    total_users = await get_users_count()
    active_subs = await get_active_subscriptions_count()
    revenue = await get_total_revenue()
    online = await vpn_service.get_online_clients()

    await callback.message.answer(
        f"📊 <b>Статистика MinVPN</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Активных подписок: <b>{active_subs}</b>\n"
        f"🟢 Онлайн сейчас: <b>{len(online)}</b>\n"
        f"💰 Общий доход: <b>{revenue:.0f}₽</b>\n\n"
        f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


# ==================== Online ====================

@admin_router.callback_query(F.data == "admin_online")
async def admin_online(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()

    online = await vpn_service.get_online_clients()

    if not online:
        text = "📈 <b>Онлайн:</b> 0 пользователей"
    else:
        text = f"📈 <b>Онлайн: {len(online)}</b>\n\n"
        for email in online[:20]:
            text += f"• <code>{email}</code>\n"
        if len(online) > 20:
            text += f"\n... и ещё {len(online) - 20}"

    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_online")],
            [InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


# ==================== Users List ====================

@admin_router.callback_query(F.data.startswith("admin_users_"))
async def admin_users_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()

    page = int(callback.data.split("_")[-1])
    per_page = 10
    users = await get_all_users(limit=per_page, offset=page * per_page)
    total = await get_users_count()

    if not users:
        await callback.message.answer("Нет пользователей.")
        return

    text = f"👥 <b>Пользователи</b> (стр. {page + 1})\n\n"
    for u in users:
        active = "🟢" if is_sub_active_str(u.get('subscription_expiry')) else "⚪"
        blocked = "🚫" if u.get('is_blocked') else ""
        text += f"{active}{blocked} <code>{u['user_id']}</code> @{u.get('username', '—')}\n"

    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users_{page - 1}"))
    if (page + 1) * per_page < total:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_users_{page + 1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")])

    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ==================== Find User ====================

@admin_router.callback_query(F.data == "admin_find_user")
async def admin_find_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("🔍 Введите Telegram ID пользователя:")
    await state.set_state(ManageUserState.waiting_user_id)


@admin_router.message(ManageUserState.waiting_user_id)
async def admin_process_find_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID.")
        return

    await _show_user_info(message, target_id)


async def _show_user_info(message: Message, target_id: int):
    user = await get_user(target_id)
    if not user:
        await message.answer(f"❌ Пользователь {target_id} не найден.")
        return

    active = is_sub_active_str(user.get('subscription_expiry'))
    status = "🟢 Активна" if active else "🔴 Не активна"
    blocked = "🚫 Заблокирован" if user.get('is_blocked') else "✅ Активен"
    expiry = user.get('subscription_expiry', '—')
    if expiry and expiry != '—':
        expiry = expiry[:16].replace('T', ' ')

    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Username: @{user.get('username', '—')}\n"
        f"📊 Статус: {blocked}\n"
        f"🌐 Подписка: {status}\n"
        f"📅 До: <code>{expiry}</code>\n"
        f"📱 Лимит устройств: {user.get('device_limit', 1)}\n"
        f"🆓 Триал: {'Использован' if user.get('trial_used') else 'Не использован'}\n"
        f"📅 Регистрация: {user.get('created_at', '—')}"
    )

    buttons = [
        [InlineKeyboardButton(text="➕ Продлить подписку", callback_data=f"admin_extend_{target_id}")],
        [InlineKeyboardButton(
            text="🚫 Заблокировать" if not user.get('is_blocked') else "✅ Разблокировать",
            callback_data=f"admin_block_{target_id}"
        )],
        [InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")],
    ]

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")


# ==================== Extend Subscription ====================

@admin_router.callback_query(F.data.startswith("admin_extend_"))
async def admin_extend(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()

    target_id = int(callback.data.split("_")[-1])
    await state.update_data(extend_user_id=target_id)
    await state.set_state(ManageUserState.waiting_extend_days)

    await callback.message.answer(
        f"📅 Сколько дней добавить пользователю <code>{target_id}</code>?\n"
        f"(Введите число, например: 30)",
        parse_mode="HTML"
    )


@admin_router.message(ManageUserState.waiting_extend_days)
async def admin_process_extend(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    target_id = data.get('extend_user_id')
    await state.clear()

    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return

    new_expiry = await extend_subscription(target_id, days)
    await record_subscription_history(target_id, "admin_extended", None, new_expiry)

    await message.answer(
        f"✅ Подписка пользователя <code>{target_id}</code> продлена на {days} дней.\n"
        f"📅 Новая дата: <code>{new_expiry[:10]}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


# ==================== Block/Unblock ====================

@admin_router.callback_query(F.data.startswith("admin_block_"))
async def admin_toggle_block(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()

    target_id = int(callback.data.split("_")[-1])
    user = await get_user(target_id)

    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        return

    currently_blocked = user.get('is_blocked', False)
    await block_user(target_id, not currently_blocked)

    action = "разблокирован" if currently_blocked else "заблокирован"
    await callback.message.answer(
        f"{'✅' if currently_blocked else '🚫'} Пользователь <code>{target_id}</code> {action}.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Админ-меню", callback_data="admin_back")]
        ]),
        parse_mode="HTML"
    )


# ==================== Broadcast ====================

@admin_router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "📢 <b>Рассылка</b>\n\nОтправьте текст сообщения для всех пользователей.\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_message)


@admin_router.message(BroadcastState.waiting_message)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена.")
        return

    await state.clear()
    users = await get_all_users(limit=10000)
    sent = 0
    failed = 0

    status_msg = await message.answer(f"📢 Отправка... 0/{len(users)}")

    for u in users:
        try:
            await bot.send_message(u['user_id'], message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

        if (sent + failed) % 20 == 0:
            try:
                await status_msg.edit_text(f"📢 Отправка... {sent + failed}/{len(users)}")
            except:
                pass

    await status_msg.edit_text(
        f"📢 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}",
        parse_mode="HTML"
    )


# ==================== Back ====================

@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("⚙️ <b>Админ-панель MinVPN</b>", reply_markup=admin_menu_kb(), parse_mode="HTML")
