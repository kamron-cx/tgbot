import asyncio
import sqlite3
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError

# --- ASOSIY SOZLAMALAR ---
TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
SUPER_ADMIN = 8753357449
MOVIE_CHANNEL_ID = -1003870500673  # Kinolar saqlanadigan kanal ID-sini shu yerga yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FSM (HOLATLAR) ---
class AdminStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_ad = State()
    waiting_for_new_channel = State()
    waiting_for_del_channel = State()
    waiting_for_new_admin = State()
    waiting_for_del_admin = State()
    waiting_for_del_movie = State()

# --- MA'LUMOTLAR BAZASI ---
def db_query(query, params=(), fetchall=False, fetchone=False):
    with sqlite3.connect("kino_pro.db") as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetchall: return cur.fetchall()
        if fetchone: return cur.fetchone()
        conn.commit()

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, msg_id INTEGER)")
    db_query("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    db_query("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    db_query("CREATE TABLE IF NOT EXISTS channels (url TEXT PRIMARY KEY)")

def is_admin(user_id):
    if user_id == SUPER_ADMIN: return True
    res = db_query("SELECT * FROM admins WHERE user_id = ?", (user_id,), fetchone=True)
    return True if res else False

# --- TUGMALAR (REPLY KEYBOARD) ---
def get_admin_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="📩 Sorov"), types.KeyboardButton(text="❓ HELP"))
    builder.row(types.KeyboardButton(text="➕ Video qo'shish"), types.KeyboardButton(text="🗑 Video o'chirish"))
    builder.row(types.KeyboardButton(text="👥 Foydalanuvchilar soni"), types.KeyboardButton(text="👮 Adminlar ro'yxati"))
    builder.row(types.KeyboardButton(text="📋 Videolar ro'yxati (admin)"))
    builder.row(types.KeyboardButton(text="📢 Kanallar"), types.KeyboardButton(text="➕ Kanal qo'shish"), types.KeyboardButton(text="➖ Kanal o'chirish"))
    builder.row(types.KeyboardButton(text="➕ Admin qo'shish"), types.KeyboardButton(text="➖ Admin o'chirish"))
    builder.adjust(2, 2, 2, 1, 3, 2)
    return builder.as_markup(resize_keyboard=True)

# --- MAJBURIY OBUNA ---
async def check_sub(user_id):
    channels = db_query("SELECT url FROM channels", fetchall=True)
    if not channels: return True
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except: continue
    return True

# --- HANDLERLAR ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    db_query("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    if is_admin(message.from_user.id):
        await message.answer("Xush kelibsiz, Admin!", reply_markup=get_admin_keyboard())
    else:
        await message.answer("🎬 Salom! Kino ko'rish uchun uning kodini yuboring.")

# ADMIN TUGMALARI UCHUN LOGIKA
@dp.message(F.text == "👥 Foydalanuvchilar soni", F.from_user.id.func(is_admin))
async def stats(message: types.Message):
    count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    await message.answer(f"📊 Foydalanuvchilar soni: {count} ta")

@dp.message(F.text == "➕ Video qo'shish", F.from_user.id.func(is_admin))
async def add_video_start(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_video)
    await message.answer("Kinoni yuboring va caption (izoh) qismiga kodini yozing:")

@dp.message(AdminStates.waiting_for_video, F.video)
async def process_video(message: types.Message, state: FSMContext):
    if not message.caption:
        await message.answer("❌ Xato! Video kodini yozish esdan chiqdi.")
        return
    try:
        sent = await bot.send_video(chat_id=MOVIE_CHANNEL_ID, video=message.video.file_id, caption=f"Kod: {message.caption}")
        db_query("INSERT OR REPLACE INTO movies VALUES (?, ?)", (message.caption.strip(), sent.message_id))
        await message.answer(f"✅ Kino saqlandi! Kod: {message.caption}")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Xatolik! Kanal ID noto'g'ri yoki bot admin emas: {e}")

@dp.message(F.text == "➕ Kanal qo'shish", F.from_user.id.func(is_admin))
async def add_chan(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_new_channel)
    await message.answer("Kanal @username yoki ID sini yuboring:")

@dp.message(AdminStates.waiting_for_new_channel)
async def process_add_chan(message: types.Message, state: FSMContext):
    db_query("INSERT OR IGNORE INTO channels VALUES (?)", (message.text.strip(),))
    await message.answer("✅ Kanal qo'shildi.")
    await state.clear()

# --- QIDIRUV (FOYDALANUVCHILAR UCHUN) ---
@dp.message(F.text)
async def search(message: types.Message):
    if is_admin(message.from_user.id) and message.text in ["➕ Video qo'shish", "🗑 Video o'chirish", "📢 Kanallar"]:
        return # Admin tugmalari qidiruvga kirmasin

    if not await check_sub(message.from_user.id):
        chans = db_query("SELECT url FROM channels", fetchall=True)
        builder = InlineKeyboardBuilder()
        for c in chans:
            url = f"https://t.me/{c[0].replace('@','')}" if "@" in c[0] else f"https://t.me/c/{str(c[0])[4:]}/1"
            builder.row(types.InlineKeyboardButton(text="A'zo bo'lish", url=url))
        await message.answer("❌ Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=builder.as_markup())
        return

    res = db_query("SELECT msg_id FROM movies WHERE code = ?", (message.text.strip(),), fetchone=True)
    if res:
        await bot.copy_message(chat_id=message.chat.id, from_chat_id=MOVIE_CHANNEL_ID, message_id=res[0])
    else:
        await message.answer("🔍 Kino topilmadi.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
