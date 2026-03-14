import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import os
import yaml
from dotenv import load_dotenv

# Загружаем секреты
load_dotenv()

# Загружаем YAML
with open('bot.yml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Берем данные из YAML
BOT_TOKEN = config.get('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in config.get('ADMIN_IDS', '').split(',') if id.strip()]
YOOMONEY_WALLET = config.get('YOOMONEY_WALLET')
PAYMENT_AMOUNT = 1000

# Проверка
if not BOT_TOKEN:
    raise ValueError("❌ Нет BOT_TOKEN в bot.yml")
if not ADMIN_IDS:
    raise ValueError("❌ Нет ADMIN_IDS в bot.yml")
if not YOOMONEY_WALLET:
    raise ValueError("❌ Нет YOOMONEY_WALLET в bot.yml")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

def init_db():
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            auth_date TIMESTAMP,
            is_authorized BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            receipt_photo TEXT,
            status TEXT DEFAULT 'pending',
            payment_date TIMESTAMP,
            verify_date TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay")],
        [InlineKeyboardButton(text="🔐 Авторизация", callback_data="auth")]
    ])
    
    await message.answer(
        f"🎁 NFT Подарки\n\n"
        f"👋 {message.from_user.first_name}\n"
        f"💰 {PAYMENT_AMOUNT} ₽\n"
        f"💳 ЮMoney\n\n"
        f"⏰ 8:00-23:00 МСК\n"
        f"👤 @Zipkask",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(Command("auth"))
async def auth_user(message: types.Message):
    user = message.from_user
    msg = await message.answer("🔐 Авторизация...")
    
    for i in range(1, 5):
        await asyncio.sleep(0.5)
        await msg.edit_text(f"🔐 {i*20}%")
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, full_name, auth_date, is_authorized)
        VALUES (?, ?, ?, ?, ?)
    ''', (user.id, user.username, user.full_name, datetime.now(), 1))
    conn.commit()
    conn.close()
    
    await msg.edit_text(
        f"✅ Авторизация успешна!\n\n"
        f"👤 ID: {user.id}\n"
        f"👤 @{user.username}",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == 'auth')
async def quick_auth(callback: types.CallbackQuery):
    await auth_user(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == 'pay')
async def pay(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"💳 Оплата ЮMoney\n\n"
        f"💰 {PAYMENT_AMOUNT} ₽\n"
        f"📱 {YOOMONEY_WALLET}\n\n"
        f"✅ После перевода нажмите кнопку",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.waiting_for_receipt)

@dp.callback_query(lambda c: c.data == 'paid')
async def paid(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📸 Отправьте фото чека")
    await state.set_state(PaymentStates.waiting_for_receipt)

@dp.callback_query(lambda c: c.data == 'back')
async def back(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data="pay")],
        [InlineKeyboardButton(text="🔐 Авторизация", callback_data="auth")]
    ])
    await callback.message.edit_text(
        f"🎁 NFT Подарки\n\n💰 {PAYMENT_AMOUNT} ₽\n💳 ЮMoney",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(PaymentStates.waiting_for_receipt)
async def receipt(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("❌ Отправьте фото!")
        return
    
    photo = message.photo[-1]
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (user_id, username, receipt_photo, payment_date, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (message.from_user.id, message.from_user.username, photo.file_id, datetime.now(), 'pending'))
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo.file_id,
                caption=f"🔔 Новый платеж!\n👤 @{message.from_user.username}\n💰 1000 ₽\n🆔 {pid}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"v_{pid}"),
                     InlineKeyboardButton(text="❌ Отклонить", callback_data=f"r_{pid}")]
                ])
            )
        except:
            pass
    
    await message.answer("✅ Чек получен!\n⏳ Ожидайте\n👤 @Zipkask")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith('v_'))
async def verify(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    pid = int(callback.data.replace('v_', ''))
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM payments WHERE id = ?', (pid,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute('UPDATE payments SET status = "verified", verify_date = ? WHERE id = ?', 
                      (datetime.now(), pid))
        conn.commit()
        await bot.send_message(user[0], f"✅ Платеж #{pid} подтвержден!\n👤 @Zipkask")
    
    conn.close()
    await callback.message.edit_caption(callback.message.caption + "\n✅ OK")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('r_'))
async def reject(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа")
        return
    
    pid = int(callback.data.replace('r_', ''))
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM payments WHERE id = ?', (pid,))
    user = cursor.fetchone()
    
    if user:
        cursor.execute('UPDATE payments SET status = "rejected" WHERE id = ?', (pid,))
        conn.commit()
        await bot.send_message(user[0], f"❌ Платеж #{pid} отклонен")
    
    conn.close()
    await callback.message.edit_caption(callback.message.caption + "\n❌ NO")
    await callback.answer()

async def main():
    init_db()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())