import telebot
from telebot import types
sqlite3 import sqlite3
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
    # Foydalanuvchilar
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)')
    # Adminlar
    cursor.execute('CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)')
    # Videolar (AUTOINCREMENT - ID o'zi oshib boradi)
    cursor.execute('CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT)')
    # Majburiy kanallar
    cursor.execute('CREATE TABLE IF NOT EXISTS channels (ch_id TEXT PRIMARY KEY)')
    
    # Asosiy adminni bazaga kiritish
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
        kb.row("📋 Videolar ro‘yxati (admin)")
    
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

# ===== VIDEO BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish")
def add_v(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "📹 Videoni yuboring (caption bilan):")
    bot.register_next_step_handler(message, save_v)

def save_v(message):
    if not message.video:
        bot.send_message(message.chat.id, "❌ Bu video emas!")
        return
    db_query('INSERT INTO videos (file_id, title) VALUES (?, ?)', (message.video.file_id, message.caption or "Video"), commit=True)
    last_id = db_query('SELECT last_insert_rowid()', fetchone=True)[0]
    bot.send_message(message.chat.id, f"✅ Video saqlandi! ID: {last_id}")

@bot.message_handler(func=lambda m: m.text == "🗑 Video o‘chirish")
def del_v(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "O'chiriladigan video ID sini yuboring:")
    bot.register_next_step_handler(message, confirm_del_v)

def confirm_del_v(message):
    if message.text.isdigit():
        db_query('DELETE FROM videos WHERE id=?', (message.text,), commit=True)
        bot.send_message(message.chat.id, "✅ Video o'chirildi.")
    else:
        bot.send_message(message.chat.id, "❗ Faqat raqam kiriting.")

# ===== VIDEO YUBORISH (RAQAM) =====
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def send_v(message):
    if not check_sub(message.from_user.id):
        channels = db_query('SELECT ch_id FROM channels', fetchall=True)
        text = "❌ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n"
        kb = types.InlineKeyboardMarkup()
        for (ch,) in channels:
            url = f"https://t.me/{ch.replace('@','')}"
            kb.add(types.InlineKeyboardButton(f"Obuna bo'lish ➕", url=url))
        bot.send_message(message.chat.id, text, reply_markup=kb)
        return

    res = db_query('SELECT file_id, title FROM videos WHERE id=?', (message.text,), fetchone=True)
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 {res[1]}\nID: {message.text}")
    else:
        bot.send_message(message.chat.id, "🚫 Bunday ID li video topilmadi.")

# ===== KANAL BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish")
def add_ch(message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "Kanal @username sini yuboring:")
    bot.register_next_step_handler(message, lambda m: (db_query('INSERT OR IGNORE INTO channels (ch_id) VALUES (?)', (m.text.strip(),), commit=True), bot.send_message(m.chat.id, "✅ Qo'shildi.")))

@bot.message_handler(func=lambda m: m.text == "➖ Kanal o‘chirish")
def del_ch(message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "O'chiriladigan kanal @username sini yuboring:")
    bot.register_next_step_handler(message, lambda m: (db_query('DELETE FROM channels WHERE ch_id=?', (m.text.strip(),), commit=True), bot.send_message(m.chat.id, "✅ O'chirildi.")))

# ===== STATISTIKA =====
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar soni")
def stats(message):
    if not is_admin(message.from_user.id): return
    count = db_query('SELECT COUNT(*) FROM users', fetchone=True)[0]
    bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {count}")

@bot.message_handler(func=lambda m: m.text == "👮 Adminlar ro‘yxati")
def list_adm(message):
    if not is_admin(message.from_user.id): return
    adms = db_query('SELECT admin_id FROM admins', fetchall=True)
    text = "👮 Adminlar ID:\n" + "\n".join([str(a[0]) for a in adms])
    bot.send_message(message.chat.id, text)

# ===== RUN =====
print("🤖 Bot SQLite bazasi bilan ishga tushdi...")
bot.infinity_polling()
