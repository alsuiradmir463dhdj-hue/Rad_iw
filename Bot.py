#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔════════════════════════════════════════════════════════════╗
║  🤖 РАДМИР ДИ - TELEGRAM БОТ                              ║
║  Версия: 1.0                                              ║
║  GitHub: https://github.com/твой-логин/radmir-di-bot     ║
╚════════════════════════════════════════════════════════════╝
"""

import os
import sys
import logging
import sqlite3
import datetime
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем токен из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("❌ ТОКЕН НЕ НАЙДЕН!")
    print("Создай файл .env и напиши: BOT_TOKEN=твой_токен")
    sys.exit(1)

# База данных
class Database:
    def __init__(self):
        self.db_path = "bot_data.db"
        self.init_db()
        
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    requests_today INTEGER DEFAULT 0,
                    last_request TEXT,
                    created_at TEXT
                )
            ''')
    
    def get_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
            return row
    
    def create_user(self, user_id, username, first_name):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, datetime.datetime.now().isoformat()))
    
    def check_request(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            today = datetime.datetime.now().date().isoformat()
            user = conn.execute('SELECT requests_today, last_request FROM users WHERE user_id = ?', (user_id,)).fetchone()
            
            if not user:
                return True
            
            requests, last = user
            
            if last != today:
                conn.execute('UPDATE users SET requests_today = 0, last_request = ? WHERE user_id = ?', (today, user_id))
                requests = 0
            
            if requests < 5:
                conn.execute('UPDATE users SET requests_today = requests_today + 1 WHERE user_id = ?', (user_id,))
                return True
            return False

db = Database()

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.create_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        f"У тебя 5 бесплатных запросов в день.\n"
        f"Используй /help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Команды:\n"
        "/start - Начать\n"
        "/help - Помощь\n"
        "/balance - Остаток\n"
        "/video текст - Видео\n"
        "/voice текст - Озвучка"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = db.get_user(update.effective_user.id)
    if user:
        remaining = 5 - (user[3] if user[3] else 0)
        await update.message.reply_text(f"⭐ Осталось запросов: {remaining}/5")
    else:
        await update.message.reply_text("Напиши /start")

async def video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример: /video красивый закат")
        return
    
    if not db.check_request(update.effective_user.id):
        await update.message.reply_text("❌ Лимит на сегодня!")
        return
    
    await update.message.reply_text(f"🎬 Генерирую: {' '.join(context.args)}...\n✅ Готово!")

async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример: /voice привет")
        return
    
    if not db.check_request(update.effective_user.id):
        await update.message.reply_text("❌ Лимит на сегодня!")
        return
    
    await update.message.reply_text(f"🎤 Озвучиваю: {' '.join(context.args)}\n✅ Готово!")

# Запуск
def main():
    print("🤖 Запуск бота...")
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("video", video))
    app.add_handler(CommandHandler("voice", voice))
    
    print("✅ Бот работает! Нажми Ctrl+C для остановки")
    app.run_polling()

if __name__ == "__main__":
    main()
