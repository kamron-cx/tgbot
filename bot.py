import asyncio
import sqlite3
import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

# Loggingni sozlash (Xatolarni kuzatish uchun)
logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
TOKEN = os.getenv("TOKEN", "8101321937:AAHwCdUofG33-yxdrYcCzoBLGM2uAfAUDPg")
SUPER_ADMIN = int(os.getenv("ADMIN", 8753357449)) 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FSM HOLATLARI ---
class AdminStates(StatesGroup):
    waiting_for_video = State()
    waiting_for_ad = State()
    waiting_for_new_channel = State()
    waiting_for_del_channel = State()
    waiting_for_del_kino = State()
    waiting_for_admin_id = State()

# --- MA'LUMOTLAR BAZASI (Xavfsizroq yondashuv) ---
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

# --- MAJBURIY OBUNA ---
async def check_sub(user_id):
    channels = db_query("SELECT url FROM channels", fetchall=True)
    if not channels: return True # Agar kanallar bo'lmasa hamma o'ta oladi
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except Exception: continue
    return True

# --- ADMIN PANEL TUGMALARI ---
def admin_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Kino", callback_data="add_kino"),
                types.InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="del_kino"))
    builder.row(types.InlineKeyboardButton(text="📢 Reklama", callback_data="send_ad"))
    builder.row(types.InlineKeyboardButton(text="🔗 Kanallar", callback_data="manage_channels"))
    builder.row(types.InlineKeyboardButton(text="📊 Statistika", callback_data="stats"))
    if user_id == SUPER_ADMIN:
        builder.row(types.InlineKeyboardButton(text="👤 Admin qo'shish", callback_data="add_adm"))
    return builder.as_markup()

# --- HANDLERLAR ---

@dp.message(CommandStart())
async def start(message: types.Message):
    db_query("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    await message.answer("🎬 Salom! Kino kodini yuboring.")

@dp.message(Command("admin"), F.from_user.id.func(is_admin))
async def admin_main(message: types.Message):
    await message.answer("🛠 Boshqaruv paneli:", reply_markup=admin_keyboard(message.from_user.id))

# --- KINO QO'SHISH ---
@dp.callback_query(F.data == "add_kino")
async def add_kino_call(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_video)
    await call.message.answer("Kino videosini yuboring va izohiga kodini yozing:")

@dp.message(AdminStates.waiting_for_video, F.video)
async def process_video_upload(message: types.Message, state: FSMContext):
    if not message.caption:
        await message.answer("❌ Xato: Videoga izoh (kod) yozing!")
        return
    
    main_chan = db_query("SELECT url FROM channels LIMIT 1", fetchone=True)
    if not main_chan:
        await message.answer("❌ Avval kamida bitta kanal qo'shing!")
        return

    try:
        sent = await bot.send_video(chat_id=main_chan[0], video=message.video.file_id, caption=f"Kod: {message.caption}")
        db_query("INSERT OR REPLACE INTO movies VALUES (?, ?)", (message.caption.strip(), sent.message_id))
        await message.answer(f"✅ Kino saqlandi! Kod: {message.caption}")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Xatolik: Bot kanalda adminmi? \n{e}")

# --- KINO O'CHIRISH ---
@dp.callback_query(F.data == "del_kino")
async def del_kino_call(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_del_kino)
    await call.message.answer("O'chirmoqchi bo'lgan kino kodingizni yuboring:")

@dp.message(AdminStates.waiting_for_del_kino)
async def process_del_kino(message: types.Message, state: FSMContext):
    db_query("DELETE FROM movies WHERE code = ?", (message.text.strip(),))
    await message.answer(f"🗑 Kod '{message.text}' bo'yicha ma'lumot o'chirildi.")
    await state.clear()

# --- STATISTIKA ---
@dp.callback_query(F.data == "stats")
async def stats_call(call: types.CallbackQuery):
    u_count = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    m_count = db_query("SELECT COUNT(*) FROM movies", fetchone=True)[0]
    await call.message.answer(f"📊 Statistika:\n👤 Foydalanuvchilar: {u_count}\n🎬 Kinolar: {m_count}")

# --- KANAL O'CHIRISH ---
@dp.callback_query(F.data == "del_chan")
async def del_chan_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_del_channel)
    await call.message.answer("O'chirmoqchi bo'lgan kanal @username'ini yuboring:")

@dp.message(AdminStates.waiting_for_del_channel)
async def del_chan_final(message: types.Message, state: FSMContext):
    db_query("DELETE FROM channels WHERE url = ?", (message.text.strip(),))
    await message.answer("🗑 Kanal ro'yxatdan o'chirildi.")
    await state.clear()

# --- OBUNA TEKSHIRISH TUGMASI ---
@dp.callback_query(F.data == "re_check")
async def re_check_sub(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.answer("Rahmat! Endi kodni yuborishingiz mumkin.", show_alert=True)
        await call.message.delete()
    else:
        await call.answer("Hali ham a'zo emassiz!", show_alert=True)

# --- QIDIRUV ---
@dp.message(F.text)
async def search_movie(message: types.Message):
    if not await check_sub(message.from_user.id):
        chans = db_query("SELECT url FROM channels", fetchall=True)
        builder = InlineKeyboardBuilder()
        for c in chans:
            clean_url = c[0].replace('@', '')
            builder.row(types.InlineKeyboardButton(text="A'zo bo'lish", url=f"https://t.me/{clean_url}"))
        builder.row(types.InlineKeyboardButton(text="Tekshirish ✅", callback_data="re_check"))
        await message.answer("❌ Kanallarga a'zo bo'lmaguningizcha kino ko'ra olmaysiz!", reply_markup=builder.as_markup())
        return

    res = db_query("SELECT msg_id FROM movies WHERE code = ?", (message.text.strip(),), fetchone=True)
    if res:
        main_chan = db_query("SELECT url FROM channels LIMIT 1", fetchone=True)
        try:
            await bot.copy_message(chat_id=message.chat.id, from_chat_id=main_chan[0], message_id=res[0])
        except Exception:
            await message.answer("❌ Videoni yuborishda xatolik. Kanalni tekshiring.")
    else:
        await message.answer("🔍 Afsuski, bunday kodli kino topilmadi.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
