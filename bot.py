import telebot
from telebot import types
import sqlite3
import os

# ===== SOZLAMALAR =====
TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584
DB_NAME = "bot_data.db"

# ===== DATABASE BILAN ISHLASH (SQLITE) =====
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    cursor.execute('CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)')
    cursor.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS channels (ch_id TEXT PRIMARY KEY)')
    cursor.execute('INSERT OR IGNORE INTO admins (admin_id) VALUES (?)', (PRIMARY_ADMIN_ID,))
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = None
    if fetchone: res = cursor.fetchone()
    if fetchall: res = cursor.fetchall()
    if commit: conn.commit()
    conn.close()
    return res

init_db()

# ===== YORDAMCHI FUNKSIYALAR =====
def is_admin(uid):
    return db_query('SELECT admin_id FROM admins WHERE admin_id=?', (uid,), fetchone=True) is not None

def check_sub(uid):
    if uid == PRIMARY_ADMIN_ID: return True
    channels = db_query('SELECT ch_id FROM channels', fetchall=True)
    if not channels: return True
    for (ch,) in channels:
        try:
            status = bot.get_chat_member(ch, uid).status
            if status in ['left', 'kicked']: return False
        except: continue
    return True

def get_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📋 Videolar ro‘yxati")
    kb.row("📤 Sorov", "❓ HELP")
    
    if is_admin(uid):
        kb.row("➕ Video qo‘shish", "🗑 Video o‘chirish")
        kb.row("👥 Foydalanuvchilar soni", "👮 Adminlar ro‘yxati")
        kb.row("📢 Reklama tarqatish") # Reklama tugmasi
    
    if uid == PRIMARY_ADMIN_ID:
        kb.row("📢 Kanallar", "➕ Kanal qo‘shish", "➖ Kanal o‘chirish")
        kb.row("➕ Admin qo‘shish", "➖ Admin o‘chirish")
    return kb

# ===== KOMANDALAR =====
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    db_query('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,), commit=True)
    bot.send_message(uid, "👋 Xush kelibsiz!", reply_markup=get_kb(uid))

# ===== REKLAMA TARQATISH =====
@bot.message_handler(func=lambda m: m.text == "📢 Reklama tarqatish")
def start_broadcast(message):
    if not is_admin(message.from_user.id): return
    msg = bot.send_message(message.chat.id, "📢 Reklama xabarini yuboring (Matn, rasm yoki video).\nBekor qilish uchun /cancel deb yozing.")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "❌ Reklama bekor qilindi.")
        return

    users = db_query('SELECT user_id FROM users', fetchall=True)
    count = 0
    error_count = 0
    status_msg = bot.send_message(message.chat.id, f"⏳ Tarqatish boshlandi...")

    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
        except:
            error_count += 1
            continue
    
    bot.send_message(message.chat.id, f"✅ Reklama yakunlandi!\n\n👤 Yetkazildi: {count}\n🚫 Bloklaganlar: {error_count}")

# ===== VIDEO VA KANAL BOSHQARUVI (SQLITE) =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish")
def add_v(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "📹 Videoni yuboring:")
    bot.register_next_step_handler(message, save_v)

def save_v(message):
    if not message.video: return
    db_query('INSERT INTO videos (file_id, title) VALUES (?, ?)', (message.video.file_id, message.caption or "Video"), commit=True)
    bot.send_message(message.chat.id, "✅ Video saqlandi.")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def send_v(message):
    if not check_sub(message.from_user.id):
        channels = db_query('SELECT ch_id FROM channels', fetchall=True)
        kb = types.InlineKeyboardMarkup()
        for (ch,) in channels:
            url = f"https://t.me/{ch.replace('@','')}"
            kb.add(types.InlineKeyboardButton("Obuna bo'lish ➕", url=url))
        bot.send_message(message.chat.id, "❌ Avval kanallarga obuna bo'ling!", reply_markup=kb)
        return
    res = db_query('SELECT file_id, title FROM videos WHERE id=?', (message.text,), fetchone=True)
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 {res[1]}\nID: {message.text}")

# (Boshqa admin funksiyalari kodingizda boridek qoladi)

print("🤖 Bot ishlamoqda...")
bot.infinity_polling()
