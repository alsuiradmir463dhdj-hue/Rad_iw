import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
MASTER_CARD = os.getenv('MASTER_CARD', '2200 1234 5678 9012')
PAYMENT_AMOUNT = 1000

# URL твоего мини-приложения на GitHub
WEBAPP_URL = "https://alsuiradmir463dhdj-hue.github.io/Rad_iw/"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

def init_db():
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            bank TEXT,
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
    # Кнопка для открытия мини-приложения
    webapp_button = InlineKeyboardButton(
        text="🎁 Открыть NFT подарки",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[webapp_button]])
    
    await message.answer(
        f"🎁 <b>NFT Подарки в Telegram</b>\n\n"
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"💰 <b>Стоимость:</b> {PAYMENT_AMOUNT} ₽\n"
        f"💳 <b>Оплата:</b> любой банк\n"
        f"⏰ <b>Выдача:</b> 8:00-23:00 МСК\n"
        f"👤 <b>Оператор:</b> @Zipkask\n\n"
        f"👇 Нажми кнопку ниже, чтобы открыть магазин",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    """Обработка данных из мини-приложения"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        
        if action == 'payment_confirmed':
            bank = data.get('bank', 'Не указан')
            
            await message.answer(
                f"✅ Запрос на оплату получен!\n\n"
                f"🏦 Банк: {bank}\n"
                f"💰 Сумма: 1000 ₽\n\n"
                f"📸 Отправьте фото чека в этот чат",
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Ошибка обработки WebApp данных: {e}")

@dp.message()
async def handle_receipt(message: types.Message):
    """Получение фото чека"""
    if not message.photo:
        return
    
    photo = message.photo[-1]
    
    # Сохраняем в БД
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payments (user_id, username, receipt_photo, payment_date, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        message.from_user.id,
        message.from_user.username,
        photo.file_id,
        datetime.now(),
        'pending'
    ))
    conn.commit()
    payment_id = cursor.lastrowid
    conn.close()
    
    # Уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo.file_id,
                caption=f"🔔 Новый платеж!\n👤 @{message.from_user.username}\n💰 1000 ₽\n🆔 #{payment_id}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"verify_{payment_id}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{payment_id}")
                    ]
                ])
            )
        except:
            pass
    
    await message.answer(
        "✅ Чек получен!\n\n"
        "⏳ Администратор проверит платеж\n"
        "⏰ Выдача NFT: 8:00-23:00 МСК\n"
        "👤 После подтверждения напишите @Zipkask"
    )

@dp.callback_query(lambda c: c.data.startswith('verify_'))
async def verify_payment(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа!")
        return
    
    payment_id = int(callback.data.replace('verify_', ''))
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM payments WHERE id = ?', (payment_id,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
        cursor.execute('UPDATE payments SET status = "verified", verify_date = ? WHERE id = ?', 
                      (datetime.now(), payment_id))
        conn.commit()
        
        await bot.send_message(
            user_id,
            f"✅ <b>Платеж #{payment_id} подтвержден!</b>\n\n"
            f"👤 Напишите @Zipkask для получения NFT\n"
            f"⏰ Режим работы: 8:00-23:00 МСК",
            parse_mode="HTML"
        )
    
    conn.close()
    await callback.message.edit_caption(
        callback.message.caption + "\n\n✅ ПОДТВЕРЖДЕНО"
    )
    await callback.answer("✅ Готово!")

@dp.callback_query(lambda c: c.data.startswith('reject_'))
async def reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет доступа!")
        return
    
    payment_id = int(callback.data.replace('reject_', ''))
    
    conn = sqlite3.connect('payments.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM payments WHERE id = ?', (payment_id,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
        cursor.execute('UPDATE payments SET status = "rejected" WHERE id = ?', (payment_id,))
        conn.commit()
        
        await bot.send_message(
            user_id,
            f"❌ <b>Платеж #{payment_id} отклонен</b>\n\n"
            f"Попробуйте снова или отправьте четкое фото чека.",
            parse_mode="HTML"
        )
    
    conn.close()
    await callback.message.edit_caption(
        callback.message.caption + "\n\n❌ ОТКЛОНЕНО"
    )
    await callback.answer("❌ Отклонено")

async def main():
    init_db()
    print("✅ Бот запущен!")
    print(f"🌐 Мини-приложение: {WEBAPP_URL}")
    print(f"👑 Админы: {ADMIN_IDS}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())