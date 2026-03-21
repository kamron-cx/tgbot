import asyncio
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError

# --- SOZLAMALAR ---
# Railway'da Environment Variables qismiga TOKEN va ADMIN qo'shing
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
    waiting_for_admin_id = State()

# --- MA'LUMOTLAR BAZASI ---
def db_query(query, params=(), fetchall=False, fetchone=False):
    conn = sqlite3.connect("kino_pro.db")
    cur = conn.cursor()
    cur.execute(query, params)
    res = None
    if fetchall: res = cur.fetchall()
    elif fetchone: res = cur.fetchone()
    conn.commit()
    conn.close()
    return res

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
    for ch in channels:
        try:
            # ch[0] - bu @username yoki ID
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]: return False
        except: continue
    return True

# --- ADMIN PANEL TUGMALARI ---
def admin_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Kino", callback_data="add_kino"),
                types.InlineKeyboardButton(text="📢 Reklama", callback_data="send_ad"))
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

# --- REKLAMA YUBORISH ---
@dp.callback_query(F.data == "send_ad")
async def ad_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_ad)
    await call.message.answer("Reklama xabarini yuboring (rasm, video yoki matn):")

@dp.message(AdminStates.waiting_for_ad)
async def ad_process(message: types.Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetchall=True)
    count = 0
    await message.answer("🚀 Reklama yuborish boshlandi...")
    for user in users:
        try:
            await bot.copy_message(chat_id=user[0], from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
            await asyncio.sleep(0.05) # Spam blokiga tushmaslik uchun
        except TelegramForbiddenError: continue
        except Exception: continue
    
    await message.answer(f"✅ Reklama {count} ta foydalanuvchiga yuborildi.")
    await state.clear()

# --- KANALLARNI BOSHQARISH ---
@dp.callback_query(F.data == "manage_channels")
async def chan_manage(call: types.CallbackQuery):
    chans = db_query("SELECT url FROM channels", fetchall=True)
    text = "📋 Hozirgi kanallar:\n\n" + "\n".join([c[0] for c in chans])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Qo'shish", callback_data="add_chan"),
                types.InlineKeyboardButton(text="🗑 O'chirish", callback_data="del_chan"))
    await call.message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "add_chan")
async def add_chan_start(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_new_channel)
    await call.message.answer("Kanal @username'ini yoki ID'sini yuboring:")

@dp.message(AdminStates.waiting_for_new_channel)
async def add_chan_final(message: types.Message, state: FSMContext):
    db_query("INSERT OR IGNORE INTO channels VALUES (?)", (message.text,))
    await message.answer("✅ Kanal qo'shildi.")
    await state.clear()

# --- KINO QIDIRISH (ASOSIY LOGIKA) ---
@dp.message(F.text)
async def search(message: types.Message):
    if not await check_sub(message.from_user.id):
        chans = db_query("SELECT url FROM channels", fetchall=True)
        builder = InlineKeyboardBuilder()
        for c in chans:
            url = f"https://t.me/{c[0].replace('@','')}" if "@" in c[0] else "https://t.me/explore"
            builder.row(types.InlineKeyboardButton(text="A'zo bo'lish", url=url))
        builder.row(types.InlineKeyboardButton(text="Tekshirish ✅", callback_data="re_check"))
        await message.answer("⚠️ Botdan foydalanish uchun kanallarga a'zo bo'ling!", reply_markup=builder.as_markup())
        return

    res = db_query("SELECT msg_id FROM movies WHERE code = ?", (message.text.strip(),), fetchone=True)
    if res:
        # Video qaysi kanalda turganini CHANNELS jadvalidan birinchisini oladi (yoki o'zingiz belgilang)
        main_chan = db_query("SELECT url FROM channels LIMIT 1", fetchone=True)
        if main_chan:
            await bot.copy_message(chat_id=message.chat.id, from_chat_id=main_chan[0], message_id=res[0])
        else:
            await message.answer("❌ Kanallar sozlanmagan!")
    else:
        await message.answer("🔍 Kino topilmadi.")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
