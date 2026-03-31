# O'rnatish: pip install aiogram aiosqlite
# Ishga tushirish: python main.py

import asyncio
import datetime
import os
import aiosqlite

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8555630882:AAGqeRiq1jU6W-fqjr_soJTH0168B7Iclsg")
ADMIN_ID = 1999635628
VPN_LINK = "https://hirbilon.net/open?sub_url=https://g3.hirbilon.net:443/yessub/p5ln8k1qld9nf0sa"
SBP_LINK = "https://www.sberbank.ru/ru/choise_bank?requisiteNumber=79990402614&bankCode=100000000111"
TON_WALLET = "UQCe2TzE4kDy9dTgiESd_xCTX9FLrVGm29JX-RqaYKhEr0kT"
USDT_WALLET = "TWJwXNwMYrGXcnbzs2Q6YeBWm4i8XkBHoh"
SUPPORT = "@Husnijan_Axi"
TRIAL_DAYS = 3
TARIFFS = {
    "1":  {"name": "1 месяц",   "price": 75,  "days": 30},
    "3":  {"name": "3 месяца",  "price": 200, "days": 90},
    "6":  {"name": "6 месяцев", "price": 350, "days": 180},
    "12": {"name": "12 месяцев","price": 500, "days": 365},
}
REF_BONUS = 10
PAYMENT_REF_BONUS = 30
MIN_WITHDRAW = 200
DB = "vpn.db"


# ========== DATABASE ==========

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, referrer INTEGER,
            balance INTEGER DEFAULT 0, trial_start TEXT, trial_end TEXT,
            paid INTEGER DEFAULT 0, subscription_end TEXT, banned INTEGER DEFAULT 0,
            reg_date TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tariff TEXT,
            amount INTEGER, method TEXT, screenshot TEXT, status TEXT DEFAULT 'pending',
            created_at TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS withdraws (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount INTEGER, wallet TEXT, status TEXT DEFAULT 'pending')""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY, discount INTEGER, uses_left INTEGER)""")
        for col in [
            ("users",    "subscription_end", "TEXT"),
            ("users",    "banned",           "INTEGER DEFAULT 0"),
            ("users",    "reg_date",         "TEXT"),
            ("payments", "created_at",       "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE {col[0]} ADD COLUMN {col[1]} {col[2]}")
            except:
                pass
        await db.commit()


async def add_user(user_id, username, referrer=None):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if not await cursor.fetchone():
            t = datetime.datetime.now()
            await db.execute(
                "INSERT INTO users (user_id, username, referrer, trial_start, trial_end, reg_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, referrer, t.isoformat(),
                 (t + datetime.timedelta(days=TRIAL_DAYS)).isoformat(), t.isoformat()))
            await db.commit()
            if referrer:
                await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?",
                                 (REF_BONUS, referrer))
                await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cursor.fetchone()


async def get_user_referrer(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT referrer FROM users WHERE user_id=?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else None


async def add_payment(user_id, tariff, amount, method, screenshot=None):
    async with aiosqlite.connect(DB) as db:
        now = datetime.datetime.now().isoformat()
        await db.execute(
            "INSERT INTO payments (user_id, tariff, amount, method, screenshot, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, tariff, amount, method, screenshot, now))
        await db.commit()


async def get_pending_payments():
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT * FROM payments WHERE status='pending'")
        return await cursor.fetchall()


async def get_payment_by_id(payment_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT * FROM payments WHERE id=?", (payment_id,))
        return await cursor.fetchone()


async def get_user_payments(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 10", (user_id,))
        return await cursor.fetchall()


async def confirm_payment(payment_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE payments SET status='confirmed' WHERE id=?", (payment_id,))
        await db.commit()


async def reject_payment(payment_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
        await db.commit()


async def activate_vpn(user_id, days):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT subscription_end FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
        now = datetime.datetime.now()
        if row and row[0]:
            try:
                current_end = datetime.datetime.fromisoformat(row[0])
                new_end = current_end + datetime.timedelta(days=days) if current_end > now \
                    else now + datetime.timedelta(days=days)
            except:
                new_end = now + datetime.timedelta(days=days)
        else:
            new_end = now + datetime.timedelta(days=days)
        await db.execute(
            "UPDATE users SET paid=1, subscription_end=? WHERE user_id=?",
            (new_end.isoformat(), user_id))
        await db.commit()
    return new_end


async def add_balance(user_id, amount):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.commit()


async def get_balance(user_id):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0


async def create_withdraw(user_id, amount, wallet):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT INTO withdraws (user_id, amount, wallet) VALUES (?, ?, ?)",
                         (user_id, amount, wallet))
        await db.commit()


async def ban_user(user_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def unban_user(user_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE banned=0")
        return [row[0] for row in await cursor.fetchall()]


async def get_promo_code(code):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT * FROM promo_codes WHERE code=? AND uses_left > 0", (code.upper(),))
        return await cursor.fetchone()


async def use_promo_code(code):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code=?", (code.upper(),))
        await db.commit()


async def add_promo_code(code, discount, uses):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO promo_codes (code, discount, uses_left) VALUES (?, ?, ?)",
            (code.upper(), discount, uses))
        await db.commit()


async def deactivate_expired():
    async with aiosqlite.connect(DB) as db:
        now = datetime.datetime.now().isoformat()
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE paid=1 AND subscription_end IS NOT NULL "
            "AND subscription_end < ?", (now,))
        expired = [row[0] for row in await cursor.fetchall()]
        await db.execute(
            "UPDATE users SET paid=0 WHERE paid=1 AND subscription_end IS NOT NULL "
            "AND subscription_end < ?", (now,))
        await db.commit()
    return expired


async def get_expiring_users(days):
    async with aiosqlite.connect(DB) as db:
        now = datetime.datetime.now()
        start = (now + datetime.timedelta(days=days - 1)).isoformat()
        end   = (now + datetime.timedelta(days=days)).isoformat()
        cursor = await db.execute(
            "SELECT user_id, username FROM users WHERE paid=1 AND subscription_end BETWEEN ? AND ?",
            (start, end))
        return await cursor.fetchall()


# ========== KEYBOARDS ==========

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Купить VPN")],
        [KeyboardButton(text="💰 Тарифы"),        KeyboardButton(text="👥 Рефералы")],
        [KeyboardButton(text="💰 Баланс"),         KeyboardButton(text="📤 Вывести деньги")],
        [KeyboardButton(text="📊 Профиль"),        KeyboardButton(text="📋 История")],
        [KeyboardButton(text="📖 Инструкция"),     KeyboardButton(text="🆘 Поддержка")]
    ], resize_keyboard=True)


def tariffs_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for key, tariff in TARIFFS.items():
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{tariff['name']} — {tariff['price']} ₽",
            callback_data=f"tariff_{key}")])
    return kb


def payment_methods_keyboard(tariff_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 СБП",  callback_data=f"sbp_{tariff_id}")],
        [InlineKeyboardButton(text="💎 TON",  callback_data=f"ton_{tariff_id}")],
        [InlineKeyboardButton(text="💎 USDT", callback_data=f"usdt_{tariff_id}")]
    ])


def payment_admin_kb(payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{payment_id}"),
        InlineKeyboardButton(text="❌ Отклонить",   callback_data=f"reject_{payment_id}")
    ]])


def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="💳 Платежи",    callback_data="payments")],
        [InlineKeyboardButton(text="📤 Выводы",     callback_data="withdraws")],
        [InlineKeyboardButton(text="📢 Рассылка",   callback_data="broadcast")],
        [InlineKeyboardButton(text="🎟 Промокоды",  callback_data="promomanage")]
    ])


def user_manage_kb(uid, banned):
    ban_text = "✅ Разбанить" if banned else "🚫 Забанить"
    ban_data = f"unban_{uid}" if banned else f"ban_{uid}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Дать подписку",   callback_data=f"givesub_{uid}"),
         InlineKeyboardButton(text="💰 Добавить баланс", callback_data=f"givebal_{uid}")],
        [InlineKeyboardButton(text=ban_text, callback_data=ban_data)]
    ])


def instruction_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 iOS",     callback_data="instr_ios")],
        [InlineKeyboardButton(text="🤖 Android", callback_data="instr_android")],
        [InlineKeyboardButton(text="💻 Windows", callback_data="instr_windows")],
        [InlineKeyboardButton(text="🍎 macOS",   callback_data="instr_macos")]
    ])


# ========== STATES ==========

class PaymentStates(StatesGroup):
    waiting_promo      = State()
    waiting_screenshot = State()

class WithdrawStates(StatesGroup):
    waiting_wallet = State()
    waiting_amount = State()

class BroadcastStates(StatesGroup):
    waiting_message = State()

class AdminStates(StatesGroup):
    waiting_give_sub       = State()
    waiting_give_bal       = State()
    waiting_promo_code     = State()
    waiting_promo_discount = State()
    waiting_promo_uses     = State()


router = Router()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def is_banned(user_id):
    user = await get_user(user_id)
    return bool(user and len(user) > 8 and user[8])


# ========== USER HANDLERS ==========

@router.message(CommandStart())
async def start(message: types.Message):
    if await is_banned(message.from_user.id):
        await message.answer("❌ Вы заблокированы.")
        return
    args = message.text.split()
    referrer = None
    if len(args) > 1:
        try:
            ref = int(args[1])
            if ref != message.from_user.id:
                referrer = ref
        except:
            pass
    await add_user(message.from_user.id, message.from_user.username, referrer)
    user = await get_user(message.from_user.id)
    trial_end = datetime.datetime.fromisoformat(user[5])
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        f"🎁 Вам доступен бесплатный VPN на {TRIAL_DAYS} дня(дней).\n"
        f"Активен до: {trial_end.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Нажмите кнопку ниже, чтобы подключить VPN.",
        reply_markup=main_menu())


@router.message(F.text == "🛒 Купить VPN")
async def buy_vpn(message: types.Message):
    if await is_banned(message.from_user.id):
        return
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
        user = await get_user(message.from_user.id)
    now = datetime.datetime.now()
    trial_end = datetime.datetime.fromisoformat(user[5])
    if user[6]:
        sub_end = user[7]
        sub_str = datetime.datetime.fromisoformat(sub_end).strftime('%d.%m.%Y') if sub_end else "—"
        await message.answer(
            f"✅ Ваша подписка VPN активна!\n📅 Действует до: {sub_str}\n\n"
            f"🔗 Ссылка для подключения:\n{VPN_LINK}",
            reply_markup=main_menu())
    elif now < trial_end:
        await message.answer(
            f"🎁 У вас активен пробный период!\nДействует до: {trial_end.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"🔗 Ссылка для подключения:\n{VPN_LINK}\n\nВыберите тариф для продления:",
            reply_markup=tariffs_keyboard())
    else:
        await message.answer("❌ У вас нет активной подписки VPN.\n\nВыберите тариф:",
                             reply_markup=tariffs_keyboard())


@router.message(F.text == "💰 Тарифы")
async def show_tariffs(message: types.Message):
    text = "📋 <b>Доступные тарифы:</b>\n\n"
    for key, tariff in TARIFFS.items():
        text += f"• {tariff['name']} — <b>{tariff['price']} ₽</b>\n"
    text += "\nДля покупки нажмите «🛒 Купить VPN»."
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "👥 Рефералы")
async def referral_info(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referrer=?", (user_id,))
        ref_count = (await cursor.fetchone())[0]
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📤 Поделиться",
            url=f"https://t.me/share/url?url={link}&text=Подключайся%20к%20VPN!")
    ]])
    await message.answer(
        f"👥 <b>Реферальная программа</b>\n\nПриглашайте друзей и получайте бонусы!\n\n"
        f"🎁 За каждого зарегистрированного друга: <b>{REF_BONUS} ₽</b>\n"
        f"💳 Если друг оплатит подписку: <b>{PAYMENT_REF_BONUS} ₽</b>\n\n"
        f"🔗 Ваша реферальная ссылка:\n<code>{link}</code>\n\n"
        f"📊 Приглашено друзей: <b>{ref_count}</b>",
        parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "💰 Баланс")
async def show_balance(message: types.Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"💰 <b>Ваш баланс:</b> {balance} ₽\n\nМинимальная сумма вывода: <b>{MIN_WITHDRAW} ₽</b>",
        parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📊 Профиль")
async def show_profile(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
        user = await get_user(message.from_user.id)
    user_id  = user[0]
    username = user[1]
    balance  = user[3]
    trial_end= user[5]
    paid     = user[6]
    sub_end  = user[7] if len(user) > 7 else None
    reg_date = user[9] if len(user) > 9 else None
    now = datetime.datetime.now()
    if paid and sub_end:
        sub_end_dt = datetime.datetime.fromisoformat(sub_end)
        days_left = (sub_end_dt - now).days
        status = (f"✅ Активна до {sub_end_dt.strftime('%d.%m.%Y')} ({days_left} дн.)"
                  if sub_end_dt > now else "❌ Истекла")
    elif now < datetime.datetime.fromisoformat(trial_end):
        trial_end_dt = datetime.datetime.fromisoformat(trial_end)
        days_left = (trial_end_dt - now).days
        status = f"🎁 Пробный до {trial_end_dt.strftime('%d.%m.%Y')} ({days_left} дн.)"
    else:
        status = "❌ Нет подписки"
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referrer=?", (user_id,))
        ref_count = (await cursor.fetchone())[0]
    reg = datetime.datetime.fromisoformat(reg_date).strftime('%d.%m.%Y') if reg_date else "—"
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{username or '—'}\n"
        f"📅 Дата регистрации: {reg}\n\n"
        f"📶 Подписка: {status}\n\n"
        f"💰 Баланс: <b>{balance} ₽</b>\n"
        f"👥 Рефералов: <b>{ref_count}</b>",
        parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📋 История")
async def show_history(message: types.Message):
    payments = await get_user_payments(message.from_user.id)
    if not payments:
        await message.answer("📋 <b>История платежей пуста.</b>",
                             parse_mode="HTML", reply_markup=main_menu())
        return
    text = "📋 <b>Последние платежи:</b>\n\n"
    statuses = {"pending": "⏳", "confirmed": "✅", "rejected": "❌"}
    methods  = {"sbp": "СБП", "ton": "TON", "usdt": "USDT"}
    for p in payments:
        pid, uid, tariff, amount, method, screenshot, status = p[0],p[1],p[2],p[3],p[4],p[5],p[6]
        created_at = p[7] if len(p) > 7 else None
        tariff_name = TARIFFS.get(tariff, {}).get("name", tariff)
        date_str = datetime.datetime.fromisoformat(created_at).strftime('%d.%m.%Y') \
            if created_at else "—"
        text += (f"{statuses.get(status, '?')} #{pid} | {tariff_name} | "
                 f"{amount} ₽ | {methods.get(method, method)} | {date_str}\n")
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📤 Вывести деньги")
async def withdraw_start(message: types.Message, state: FSMContext):
    balance = await get_balance(message.from_user.id)
    if balance < MIN_WITHDRAW:
        await message.answer(
            f"❌ Недостаточно средств.\nБаланс: <b>{balance} ₽</b>\nМинимум: <b>{MIN_WITHDRAW} ₽</b>",
            parse_mode="HTML", reply_markup=main_menu())
        return
    await state.set_state(WithdrawStates.waiting_wallet)
    await message.answer(
        f"💸 <b>Вывод средств</b>\n\nБаланс: <b>{balance} ₽</b>\n\n"
        f"Введите адрес кошелька (TON или USDT TRC-20):", parse_mode="HTML")


@router.message(WithdrawStates.waiting_wallet)
async def withdraw_wallet(message: types.Message, state: FSMContext):
    await state.update_data(wallet=message.text)
    await state.set_state(WithdrawStates.waiting_amount)
    balance = await get_balance(message.from_user.id)
    await message.answer(f"Введите сумму для вывода (максимум: {balance} ₽):")


@router.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Пожалуйста, введите число.")
        return
    balance = await get_balance(message.from_user.id)
    if amount > balance:
        await message.answer(f"❌ Недостаточно средств. Баланс: {balance} ₽")
        return
    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимальная сумма: {MIN_WITHDRAW} ₽")
        return
    data = await state.get_data()
    wallet = data["wallet"]
    await create_withdraw(message.from_user.id, amount, wallet)
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id=?",
                         (amount, message.from_user.id))
        await db.commit()
    await message.bot.send_message(ADMIN_ID,
        f"💸 <b>Новая заявка на вывод!</b>\n\n"
        f"👤 @{message.from_user.username} (ID: {message.from_user.id})\n"
        f"💰 Сумма: <b>{amount} ₽</b>\n💳 Кошелёк: <code>{wallet}</code>",
        parse_mode="HTML")
    await state.clear()
    await message.answer(
        f"✅ Заявка принята!\nСумма: <b>{amount} ₽</b>\nКошелёк: <code>{wallet}</code>\n\n"
        f"Обработаем в ближайшее время.",
        parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📖 Инструкция")
async def instruction(message: types.Message):
    await message.answer(
        "📖 <b>Инструкция по подключению VPN</b>\n\nВыберите вашу платформу:",
        parse_mode="HTML", reply_markup=instruction_kb())


@router.callback_query(F.data == "instr_ios")
async def instr_ios(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📱 <b>Инструкция для iOS</b>\n\n"
        "1️⃣ Скачайте <b>V2Box</b> или <b>Shadowrocket</b> из App Store\n"
        "2️⃣ Нажмите «🛒 Купить VPN» и оформите подписку\n"
        "3️⃣ После активации скопируйте ссылку для подключения\n"
        "4️⃣ В приложении нажмите «+» → «Импорт из буфера обмена»\n"
        "5️⃣ Нажмите «Подключить» и разрешите VPN-конфигурацию\n\n"
        f"❓ Поддержка: {SUPPORT}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="instr_back")
        ]]))
    await callback.answer()


@router.callback_query(F.data == "instr_android")
async def instr_android(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤖 <b>Инструкция для Android</b>\n\n"
        "1️⃣ Скачайте <b>V2RayNG</b> из Google Play или APKPure\n"
        "2️⃣ Нажмите «🛒 Купить VPN» и оформите подписку\n"
        "3️⃣ После активации скопируйте ссылку для подключения\n"
        "4️⃣ В V2RayNG нажмите «+» → «Импорт из буфера обмена»\n"
        "5️⃣ Нажмите кнопку запуска (треугольник)\n\n"
        f"❓ Поддержка: {SUPPORT}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="instr_back")
        ]]))
    await callback.answer()


@router.callback_query(F.data == "instr_windows")
async def instr_windows(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💻 <b>Инструкция для Windows</b>\n\n"
        "1️⃣ Скачайте <b>V2RayN</b> с GitHub (github.com/2dust/v2rayN)\n"
        "2️⃣ Нажмите «🛒 Купить VPN» и оформите подписку\n"
        "3️⃣ После активации скопируйте ссылку для подключения\n"
        "4️⃣ V2RayN: Серверы → Импорт из буфера обмена\n"
        "5️⃣ Выберите сервер va нажмите «Запустить»\n\n"
        f"❓ Поддержка: {SUPPORT}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="instr_back")
        ]]))
    await callback.answer()


@router.callback_query(F.data == "instr_macos")
async def instr_macos(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🍎 <b>Инструкция для macOS</b>\n\n"
        "1️⃣ Скачайте <b>V2Box</b> из Mac App Store\n"
        "2️⃣ Нажмите «🛒 Купить VPN» и оформите подписку\n"
        "3️⃣ После активации скопируйте ссылку для подключения\n"
        "4️⃣ V2Box: нажмите «+» → «Вставить из буфера обмена»\n"
        "5️⃣ Нажмите «Подключить»\n\n"
        f"❓ Поддержка: {SUPPORT}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="instr_back")
        ]]))
    await callback.answer()


@router.callback_query(F.data == "instr_back")
async def instr_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📖 <b>Инструкция по подключению VPN</b>\n\nВыберите вашу платформу:",
        parse_mode="HTML", reply_markup=instruction_kb())
    await callback.answer()


@router.message(F.text == "🆘 Поддержка")
async def support(message: types.Message):
    await message.answer(
        f"🆘 <b>Поддержка</b>\n\nОбратитесь к администратору:\n\n👤 {SUPPORT}",
        parse_mode="HTML", reply_markup=main_menu())


# ========== TARIFF / PROMO / PAYMENT FLOW ==========

@router.callback_query(F.data.startswith("tariff_"))
async def tariff_selected(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split("_")[1]
    tariff = TARIFFS.get(tariff_id)
    if not tariff:
        await callback.answer("Тариф не найден")
        return
    await state.update_data(tariff_id=tariff_id, amount=tariff["price"])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Ввести промокод",
                              callback_data=f"enterpromo_{tariff_id}")],
        [InlineKeyboardButton(text="➡️ Продолжить без промокода",
                              callback_data=f"skippromo_{tariff_id}")]
    ])
    await callback.message.edit_text(
        f"✅ Вы выбрали: <b>{tariff['name']}</b>\n"
        f"💰 Стоимость: <b>{tariff['price']} ₽</b>\n\nЕсть промокод?",
        parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("enterpromo_"))
async def enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentStates.waiting_promo)
    await callback.message.edit_text("🎟 Введите промокод:")
    await callback.answer()


@router.message(PaymentStates.waiting_promo)
async def check_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    promo = await get_promo_code(code)
    data = await state.get_data()
    tariff_id = data["tariff_id"]
    tariff = TARIFFS.get(tariff_id)
    if not promo:
        await state.update_data(amount=tariff["price"])
        await state.set_state(None)
        await message.answer(
            "❌ Промокод недействителен или исчерпан.\n\nВыберите способ оплаты:",
            reply_markup=payment_methods_keyboard(tariff_id))
        return
    discount = promo[1]
    new_price = max(1, tariff["price"] - discount)
    await use_promo_code(code)
    await state.update_data(amount=new_price)
    await state.set_state(None)
    await message.answer(
        f"✅ Промокод применён! Скидка: <b>{discount} ₽</b>\n"
        f"💰 Итоговая цена: <b>{new_price} ₽</b>\n\nВыберите способ оплаты:",
        parse_mode="HTML", reply_markup=payment_methods_keyboard(tariff_id))


@router.callback_query(F.data.startswith("skippromo_"))
async def skip_promo(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split("_")[1]
    tariff = TARIFFS.get(tariff_id)
    await state.update_data(tariff_id=tariff_id, amount=tariff["price"])
    await callback.message.edit_text(
        f"✅ Вы выбрали: <b>{tariff['name']}</b>\n"
        f"💰 Стоимость: <b>{tariff['price']} ₽</b>\n\nВыберите способ оплаты:",
        parse_mode="HTML", reply_markup=payment_methods_keyboard(tariff_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sbp_"))
async def payment_sbp(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split("_")[1]
    data = await state.get_data()
    amount = data.get("amount", TARIFFS.get(tariff_id, {}).get("price"))
    await state.update_data(tariff_id=tariff_id, method="sbp", amount=amount)
    await state.set_state(PaymentStates.waiting_screenshot)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💳 Перейти к оплате через СБП", url=SBP_LINK)
    ]])
    await callback.message.edit_text(
        f"💳 <b>Оплата через СБП</b>\n\nСумма: <b>{amount} ₽</b>\n\n"
        f"Нажмите кнопку ниже для перехода к оплате.\n\n"
        f"После оплаты отправьте <b>скриншот чека</b>:",
        parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ton_"))
async def payment_ton(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split("_")[1]
    data = await state.get_data()
    amount = data.get("amount", TARIFFS.get(tariff_id, {}).get("price"))
    await state.update_data(tariff_id=tariff_id, method="ton", amount=amount)
    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.message.edit_text(
        f"💎 <b>Оплата через TON</b>\n\nСумма: <b>{amount} ₽</b> (в эквиваленте TON)\n\n"
        f"📬 Адрес TON кошелька:\n<code>{TON_WALLET}</code>\n\n"
        f"После оплаты отправьте <b>скриншот чека</b>:",
        parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("usdt_"))
async def payment_usdt(callback: types.CallbackQuery, state: FSMContext):
    tariff_id = callback.data.split("_")[1]
    data = await state.get_data()
    amount = data.get("amount", TARIFFS.get(tariff_id, {}).get("price"))
    await state.update_data(tariff_id=tariff_id, method="usdt", amount=amount)
    await state.set_state(PaymentStates.waiting_screenshot)
    await callback.message.edit_text(
        f"💎 <b>Оплата через USDT (TRC-20)</b>\n\nСумма: <b>{amount} ₽</b> (в эквиваленте USDT)\n\n"
        f"📬 Адрес USDT кошелька:\n<code>{USDT_WALLET}</code>\n\n"
        f"После оплаты отправьте <b>скриншот чека</b>:",
        parse_mode="HTML")
    await callback.answer()


@router.message(PaymentStates.waiting_screenshot, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tariff = TARIFFS.get(data["tariff_id"])
    photo_id = message.photo[-1].file_id
    await add_payment(message.from_user.id, data["tariff_id"], data["amount"], data["method"], photo_id)
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT id FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (message.from_user.id,))
        payment_id = (await cursor.fetchone())[0]
    methods = {"sbp": "СБП", "ton": "TON", "usdt": "USDT (TRC-20)"}
    await message.bot.send_photo(ADMIN_ID, photo=photo_id,
        caption=(f"💳 <b>Новая заявка на оплату!</b>\n\n🆔 ID: #{payment_id}\n"
                 f"👤 @{message.from_user.username} (ID: {message.from_user.id})\n"
                 f"📦 Тариф: {tariff['name']}\n💰 Сумма: {data['amount']} ₽\n"
                 f"💳 Способ: {methods.get(data['method'], data['method'])}"),
        parse_mode="HTML", reply_markup=payment_admin_kb(payment_id))
    await state.clear()
    await message.answer(
        "✅ <b>Чек отправлен!</b>\n\nАдминистратор активирует подписку в течение 5–15 минут.",
        parse_mode="HTML", reply_markup=main_menu())


@router.message(PaymentStates.waiting_screenshot)
async def wrong_screenshot(message: types.Message):
    await message.answer("📸 Пожалуйста, отправьте <b>фото</b> чека об оплате.", parse_mode="HTML")


# ========== ADMIN PANEL ==========

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа.")
        return
    await message.answer("👨‍💼 <b>Панель администратора</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    async with aiosqlite.connect(DB) as db:
        total     = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        paid      = (await (await db.execute("SELECT COUNT(*) FROM users WHERE paid=1")).fetchone())[0]
        banned    = (await (await db.execute("SELECT COUNT(*) FROM users WHERE banned=1")).fetchone())[0]
        pending   = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")).fetchone())[0]
        confirmed = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='confirmed'")).fetchone())[0]
        income    = (await (await db.execute(
            "SELECT SUM(amount) FROM payments WHERE status='confirmed'")).fetchone())[0] or 0
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        new_today = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE reg_date LIKE ?", (f"{today}%",))).fetchone())[0]
        month = datetime.datetime.now().strftime('%Y-%m')
        new_month = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE reg_date LIKE ?", (f"{month}%",))).fetchone())[0]
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👤 Всего пользователей: <b>{total}</b>\n"
        f"🆕 Новых сегодня: <b>{new_today}</b>\n"
        f"📅 Новых в этом месяце: <b>{new_month}</b>\n"
        f"🚫 Заблокировано: <b>{banned}</b>\n\n"
        f"✅ С активной подпиской: <b>{paid}</b>\n\n"
        f"⏳ Ожидают подтверждения: <b>{pending}</b>\n"
        f"✅ Подтверждённых: <b>{confirmed}</b>\n"
        f"💰 Доход: <b>{income} ₽</b>",
        parse_mode="HTML", reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "payments")
async def show_payments(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    payments = await get_pending_payments()
    text = ("💳 Ожидающих платежей нет." if not payments
            else f"💳 <b>Ожидающих платежей: {len(payments)}</b>\n\nЧеки отправлены отдельными сообщениями.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "withdraws")
async def show_withdraws(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT * FROM withdraws WHERE status='pending'")
        withdraws = await cursor.fetchall()
    if not withdraws:
        await callback.message.edit_text("📤 Заявок на вывод нет.", reply_markup=admin_panel_kb())
    else:
        text = f"📤 <b>Заявки на вывод: {len(withdraws)}</b>\n\n"
        for w in withdraws:
            text += f"🆔 #{w[0]} | 👤 ID: {w[1]} | 💰 {w[2]} ₽ | 💳 <code>{w[3]}</code>\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(BroadcastStates.waiting_message)
    await callback.message.answer("📢 Введите сообщение для рассылки всем пользователям:")
    await callback.answer()


@router.message(BroadcastStates.waiting_message)
async def do_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    users = await get_all_users()
    sent, failed = 0, 0
    for uid in users:
        try:
            await message.bot.send_message(uid,
                f"📢 <b>Сообщение от администратора:</b>\n\n{message.text}",
                parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    await state.clear()
    await message.answer(f"✅ Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}")


@router.callback_query(F.data == "promomanage")
async def promo_manage(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_promo_code)
    await callback.message.answer("🎟 Создание промокода.\n\nВведите код (например: SALE20):")
    await callback.answer()


@router.message(AdminStates.waiting_promo_code)
async def promo_get_code(message: types.Message, state: FSMContext):
    await state.update_data(promo_code=message.text.strip().upper())
    await state.set_state(AdminStates.waiting_promo_discount)
    await message.answer("Введите размер скидки в рублях (например: 20):")


@router.message(AdminStates.waiting_promo_discount)
async def promo_get_discount(message: types.Message, state: FSMContext):
    try:
        discount = int(message.text)
    except:
        await message.answer("❌ Введите число.")
        return
    await state.update_data(promo_discount=discount)
    await state.set_state(AdminStates.waiting_promo_uses)
    await message.answer("Введите количество использований:")


@router.message(AdminStates.waiting_promo_uses)
async def promo_get_uses(message: types.Message, state: FSMContext):
    try:
        uses = int(message.text)
    except:
        await message.answer("❌ Введите число.")
        return
    data = await state.get_data()
    await add_promo_code(data["promo_code"], data["promo_discount"], uses)
    await state.clear()
    await message.answer(
        f"✅ Промокод создан!\n\n"
        f"🎟 Код: <code>{data['promo_code']}</code>\n"
        f"💰 Скидка: {data['promo_discount']} ₽\n"
        f"🔢 Использований: {uses}",
        parse_mode="HTML")


@router.message(Command("user"))
async def manage_user(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /user <ID>")
        return
    try:
        uid = int(args[1])
    except:
        await message.answer("❌ Неверный ID.")
        return
    user = await get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        return
    username = user[1]
    balance  = user[3]
    paid     = user[6]
    sub_end  = user[7] if len(user) > 7 else None
    banned   = user[8] if len(user) > 8 else 0
    now = datetime.datetime.now()
    if paid and sub_end:
        sub_end_dt = datetime.datetime.fromisoformat(sub_end)
        status = (f"✅ до {sub_end_dt.strftim **...**

_This response is too long to display in full._
