import logging
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- SOZLAMALAR ---
API_TOKEN = '7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs'
CHIEF_ADMIN = 5909932584  # O'zingizning ID raqamingiz

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('database.sqlite')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, caption TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY, link TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- ADMIN TEKSHIRUVI ---
async def is_admin(user_id):
    if user_id == CHIEF_ADMIN: return True
    conn = sqlite3.connect('database.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res is not None

# --- MAJBURIY OBUNA ---
async def check_sub(user_id):
    conn = sqlite3.connect('database.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT id, link FROM channels")
    channels = cur.fetchall()
    conn.close()
    
    for ch_id, link in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']: return False, link
        except: continue
    return True, None

# --- FOYDALANUVCHI QISMI ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # Foydalanuvchini bazaga qo'shish
    conn = sqlite3.connect('database.sqlite')
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()

    is_ok, link = await check_sub(message.from_user.id)
    if not is_ok:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=link)]])
        return await message.answer("Botdan foydalanish uchun kanalga a'zo bo'ling!", reply_markup=kb)

    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="🆘 Help"), types.KeyboardButton(text="📩 So'rov yuborish")]
    ], resize_keyboard=True)
    
    if await is_admin(message.from_user.id):
        kb.keyboard.append([types.KeyboardButton(text="👨‍💻 Admin Panel")])
        
    await message.answer("Xush kelibsiz! Video ID raqamini yuboring.", reply_markup=kb)

@dp.message(F.text == "🆘 Help")
async def help_fn(message: types.Message):
    await message.answer("Botdan foydalanish uchun video ID raqamini yuboring. Masalan: 12\nAdmin bilan bog'lanish uchun 'So'rov yuborish' tugmasini bosing.")

# Video qidirish (Faqat raqam yuborsa)
@dp.message(F.text.isdigit())
async def get_video(message: types.Message):
    conn = sqlite3.connect('database.sqlite')
    cur = conn.cursor()
    cur.execute("SELECT file_id, caption FROM videos WHERE id=?", (message.text,))
    res = cur.fetchone()
    conn.close()
    if res:
        await message.answer_video(video=res[0], caption=res[1])
    else:
        await message.answer("Bunday ID dagi video topilmadi.")

# --- ADMIN FUNKSIYALARI ---
@dp.message(F.text == "👨‍💻 Admin Panel")
async def admin_menu(message: types.Message):
    if not await is_admin(message.from_user.id): return
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="➕ Video qo'shish"), types.KeyboardButton(text="🗑 Video o'chirish")],
        [types.KeyboardButton(text="📊 Statistika"), types.KeyboardButton(text="📢 Reklama")],
        [types.KeyboardButton(text="➕ Admin qo'shish"), types.KeyboardButton(text="➕ Kanal qo'shish")]
    ], resize_keyboard=True)
    await message.answer("Admin paneliga xush kelibsiz", reply_markup=kb)

# Video qo'shish logikasi (Sodda variant)
@dp.message(F.video)
async def save_vid(message: types.Message):
    if await is_admin(message.from_user.id):
        conn = sqlite3.connect('database.sqlite')
        cur = conn.cursor()
        cur.execute("INSERT INTO videos (file_id, caption) VALUES (?, ?)", (message.video.file_id, message.caption))
        v_id = cur.lastrowid
        conn.commit()
        conn.close()
        await message.answer(f"Video saqlandi! ID: {v_id}")

# --- ISHGA TUSHIRISH ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
