import telebot
from telebot import types
import sqlite3
import os

# ===== SOZLAMALAR =====
TOKEN = os.getenv("BOT_TOKEN") or "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584 

# ===== DATABASE SOZLASH =====
def init_db():
    conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, genre TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, gender TEXT, age_range TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()

def is_admin(uid: int):
    db_cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (uid,))
    return db_cursor.fetchone() is not None

# ===== KLAVIATURALAR =====
def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📂 Janrlar bo'yicha", "📋 Kinolar ro'yxati")
    kb.row("📤 So'rov yuborish", "❓ HELP")
    if is_admin(uid):
        kb.row("➕ Video qo'shish", "🗑 Video o'chirish")
        kb.row("➕ Admin qo'shish", "➖ Admin o'chirish")
        kb.row("📢 Kanal qo'shish", "❌ Kanal o'chirish")
        kb.row("📊 Statistika")
    return kb

# ===== VIDEO QO'SHISH (ISHLYDIGAN QISMI) =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo'shish")
def add_video_v1(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "📹 Menga videoni yuboring:")
    bot.register_next_step_handler(message, add_video_v2)

def add_video_v2(message):
    if not message.video:
        bot.send_message(message.chat.id, "❌ Bu video emas. Qaytadan urinib ko'ring.")
        return
    file_id = message.video.file_id
    bot.send_message(message.chat.id, "📝 Video nomini (caption) yozing:")
    bot.register_next_step_handler(message, add_video_v3, file_id)

def add_video_v3(message, file_id):
    title = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("🎬 Jangari", "🍿 Komediya", "😱 Qo'rqinchli", "🧸 Multfilm")
    bot.send_message(message.chat.id, "📂 Janrni tanlang:", reply_markup=kb)
    bot.register_next_step_handler(message, add_video_final, file_id, title)

def add_video_final(message, file_id, title):
    genre = message.text
    db_cursor.execute("INSERT INTO movies (file_id, title, genre) VALUES (?, ?, ?)", (file_id, title, genre))
    db_conn.commit()
    bot.send_message(message.chat.id, f"✅ Video saqlandi! ID: {db_cursor.lastrowid}", reply_markup=main_keyboard(message.from_user.id))

# ===== ADMIN QO'SHISH =====
@bot.message_handler(func=lambda m: m.text == "➕ Admin qo'shish")
def add_admin_v1(message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "🆔 Yangi admin ID sini yuboring:")
    bot.register_next_step_handler(message, add_admin_v2)

def add_admin_v2(message):
    if message.text.isdigit():
        db_cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (int(message.text),))
        db_conn.commit()
        bot.send_message(message.chat.id, "✅ Admin qo'shildi!")
    else:
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID format.")

# ===== SO'ROV YUBORISH =====
@bot.message_handler(func=lambda m: m.text == "📤 So'rov yuborish")
def request_v1(message):
    bot.send_message(message.chat.id, "📩 Qaysi kinoni qidiryapsiz? Nomi yoki qisqacha ma'lumot yuboring:")
    bot.register_next_step_handler(message, request_v2)

def request_v2(message):
    # Adminlarga yuborish
    db_cursor.execute("SELECT admin_id FROM admins")
    admins = db_cursor.fetchall()
    for adm in admins:
        bot.send_message(adm[0], f"📥 **Yangi so'rov!**\n👤 Kimdan: {message.from_user.id}\n📝 Matn: {message.text}")
    bot.send_message(message.chat.id, "✅ So'rovingiz adminlarga yuborildi.")

# ===== JANRLAR BO'YICHA =====
@bot.message_handler(func=lambda m: m.text == "📂 Janrlar bo'yicha")
def genres_v1(message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎬 Jangari", "🍿 Komediya", "😱 Qo'rqinchli", "🧸 Multfilm", "⬅️ Orqaga")
    bot.send_message(message.chat.id, "Janrni tanlang:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["🎬 Jangari", "🍿 Komediya", "😱 Qo'rqinchli", "🧸 Multfilm"])
def genres_v2(message):
    db_cursor.execute("SELECT id, title FROM movies WHERE genre = ?", (message.text,))
    rows = db_cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "😔 Bu janrda kinolar hali yo'q.")
    else:
        res = f"📂 **{message.text} janridagi kinolar:**\n\n"
        for r in rows: res += f"🆔 {r[0]} | {r[1]}\n"
        bot.send_message(message.chat.id, res)

# ===== VIDEO O'CHIRISH =====
@bot.message_handler(func=lambda m: m.text == "🗑 Video o'chirish")
def del_movie_v1(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "🆔 O'chirmoqchi bo'lgan video ID sini yuboring:")
    bot.register_next_step_handler(message, del_movie_v2)

def del_movie_v2(message):
    if message.text.isdigit():
        db_cursor.execute("DELETE FROM movies WHERE id = ?", (int(message.text),))
        db_conn.commit()
        bot.send_message(message.chat.id, "✅ Video o'chirildi.")
    else:
        bot.send_message(message.chat.id, "❌ ID raqam bo'lishi kerak.")

# ===== ORQAGA TUGMASI =====
@bot.message_handler(func=lambda m: m.text == "⬅️ Orqaga")
def back_cmd(message):
    bot.send_message(message.chat.id, "Bosh menyu", reply_markup=main_keyboard(message.from_user.id))

# Boshqa barcha tugmalar (Start, Help, Statistika) uchun ham shunday handlerlar qo'shishingiz kerak...

bot.infinity_polling()
