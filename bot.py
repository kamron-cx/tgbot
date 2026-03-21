import telebot
from telebot import types
import sqlite3
import time

# 🔑 SOZLAMALAR
TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)

PRIMARY_ADMIN_ID = 5909932584 
MOVIE_CHANNEL_ID = -1003897276958  # Rasmda ko'rsatilgan ID raqamingiz

# ===== SQLite Bazani sozlash =====
def init_db():
    conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       file_id TEXT, title TEXT, genre TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    # O'zingizning kanalingizni yuzernamesini shu yerga yozing
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("sub_channel", "@Sizning_Kanalingiz"))
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()
db_cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
db_conn.commit()

# ===== Yordamchi funksiyalar =====
def get_sub_channel():
    db_cursor.execute("SELECT value FROM settings WHERE key = 'sub_channel'")
    res = db_cursor.fetchone()
    return res[0] if res and res[0] is not None else None

def is_admin(uid: int) -> bool:
    db_cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (uid,))
    return db_cursor.fetchone() is not None

def check_sub(uid: int):
    channel = get_sub_channel()
    if not channel or uid == PRIMARY_ADMIN_ID: return True
    try:
        status = bot.get_chat_member(channel, uid).status
        return status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Obuna tekshirishda xato: {e}")
        return True # Xato bo'lsa bot to'xtab qolmasligi uchun o'tkazib yuboramiz

def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🎬 Barcha kinolar"), types.KeyboardButton("📂 Janrlar bo'yicha"))
    kb.add(types.KeyboardButton("📤 Kino so'rash"), types.KeyboardButton("❓ Yordam"))
    if is_admin(uid):
        kb.add(types.KeyboardButton("➕ Kino qo'shish"), types.KeyboardButton("📢 Reklama tarqatish"))
        kb.add(types.KeyboardButton("📊 Statistika"), types.KeyboardButton("⚙️ Sozlamalar"))
    return kb

# ===== Admin: Sozlamalar =====
@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def channel_settings(message):
    if not is_admin(message.from_user.id): return
    current = get_sub_channel()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 Kanalni yangilash", callback_data="change_channel"))
    kb.add(types.InlineKeyboardButton("❌ Obunani o'chirish", callback_data="off_channel"))
    bot.send_message(message.chat.id, f"⚙️ **Sozlamalar bo'limi**\n\n📢 Hozirgi majburiy kanal: `{current}`", 
                     parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "change_channel")
def ask_new_channel(call):
    bot.send_message(call.message.chat.id, "🛰 **Yangi kanal yuzerini yuboring:**\n(Masalan: @kino_kanali)")
    bot.register_next_step_handler(call.message, update_channel)

def update_channel(message):
    new_ch = message.text.strip()
    if new_ch.startswith("@"):
        db_cursor.execute("UPDATE settings SET value = ? WHERE key = 'sub_channel'", (new_ch,))
        db_conn.commit()
        bot.send_message(message.chat.id, f"✅ **Muvaffaqiyatli!** Majburiy kanal {new_ch} ga o'zgartirildi.")
    else:
        bot.send_message(message.chat.id, "⚠️ **Xatolik!** Kanal yuzeri @ belgisi bilan boshlanishi kerak.")

@bot.callback_query_handler(func=lambda c: c.data == "off_channel")
def turn_off_sub(call):
    db_cursor.execute("UPDATE settings SET value = NULL WHERE key = 'sub_channel'")
    db_conn.commit()
    bot.edit_message_text("❌ Majburiy obuna o'chirildi.", call.message.chat.id, call.message.message_id)

# ===== Obuna tekshiruvi (START buyrug'idan tashqari hamma narsa uchun) =====
@bot.message_handler(func=lambda m: not check_sub(m.from_user.id) and m.text != "/start")
def sub_check_handler(message):
    channel = get_sub_channel()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ A'zo bo'lish", url=f"https://t.me/{channel[1:]}"))
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_again"))
    bot.send_message(message.chat.id, f"🛑 **Diqqat!**\n\nBotdan foydalanish uchun {channel} kanaliga a'zo bo'lishingiz shart!", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check_again")
def check_again_btn(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "🎉 **Rahmat!** Kirish ruxsat etildi.", 
                         reply_markup=main_keyboard(call.from_user.id))
    else:    
    
