import telebot
from telebot import types
import sqlite3
import os

# ===== SOZLAMALAR =====
# Railway'da Environment Variables qismiga BOT_TOKEN qo'shishni unutmang
TOKEN = os.getenv("BOT_TOKEN") or "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584 

# ===== DATABASE SOZLASH =====
def init_db():
    conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, genre TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, city TEXT, gender TEXT, age TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("sub_channel", "@kino_olami"))
    cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()

# ===== YORDAMCHI FUNKSIYALAR =====
def is_admin(uid: int) -> bool:
    db_cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (uid,))
    return db_cursor.fetchone() is not None

def get_sub_channel():
    db_cursor.execute("SELECT value FROM settings WHERE key = 'sub_channel'")
    res = db_cursor.fetchone()
    return res[0] if res else None

def check_sub(uid: int):
    channel = get_sub_channel()
    if not channel or channel == "OFF": return True
    try:
        status = bot.get_chat_member(channel, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return True

# ===== KLAVIATURALAR =====
def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📋 Kinolar ro'yxati", "📂 Janrlar bo'yicha")
    kb.row("📤 So'rov yuborish", "❓ HELP")
    if is_admin(uid):
        kb.row("➕ Video qo'shish", "🗑 Video o'chirish")
        kb.row("➕ Admin qo'shish", "➖ Admin o'chirish")
        kb.row("📢 Kanalni sozlash", "📊 Statistika")
    return kb

# ===== START VA RO'YXATDAN O'TISH =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    db_cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not db_cursor.fetchone():
        bot.send_message(uid, "👋 Salom! Botdan foydalanish uchun ro'yxatdan o'ting.\n\n📍 **Qaysi shaharda yashaysiz?**")
        bot.register_next_step_handler(message, get_city)
    else:
        if not check_sub(uid): return show_sub_msg(message)
        bot.send_message(uid, "Kino kodini yuboring:", reply_markup=main_keyboard(uid))

def get_city(message):
    city = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Erkak", "Ayol")
    bot.send_message(message.chat.id, "👤 Jinsingizni tanlang:", reply_markup=kb)
    bot.register_next_step_handler(message, get_gender, city)

def get_gender(message, city):
    gender = message.text
    bot.send_message(message.chat.id, "📅 Yoshingizni yozing:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, finalize_reg, city, gender)

def finalize_reg(message, city, gender):
    age = message.text
    db_cursor.execute("INSERT INTO users (user_id, city, gender, age) VALUES (?, ?, ?, ?)", (message.from_user.id, city, gender, age))
    db_conn.commit()
    bot.send_message(message.chat.id, "✅ Ro'yxatdan o'tdingiz!", reply_markup=main_keyboard(message.from_user.id))

# ===== KINOLAR RO'YXATI (Guruhlangan) =====
@bot.message_handler(func=lambda m: m.text == "📋 Kinolar ro'yxati")
def list_movies(message):
    if not check_sub(message.from_user.id): return show_sub_msg(message)
    genres = ["Kino", "Multfilm", "Serial", "Koreys"]
    text = "📋 **Mavjud kinolar ro'yxati:**\n\n"
    for g in genres:
        db_cursor.execute("SELECT id, title FROM movies WHERE genre = ?", (g,))
        rows = db_cursor.fetchall()
        text += f"🎬 **{g} ({len(rows)} ta):**\n"
        if rows:
            for r in rows: text += f"🆔 {r[0]} | {r[1]}\n"
        else: text += "— Hozircha bo'sh\n"
        text += "------------------------\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ===== ADMIN: VIDEO QO'SHISH =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo'shish" and is_admin(m.from_user.id))
def add_video_v1(message):
    bot.send_message(message.chat.id, "📹 Videoni yuboring:")
    bot.register_next_step_handler(message, add_video_v2)

def add_video_v2(message):
    if not message.video: return bot.send_message(message.chat.id, "❌ Faqat video yuboring!")
    file_id = message.video.file_id
    bot.send_message(message.chat.id, "📝 Video nomini yozing:")
    bot.register_next_step_handler(message, add_video_v3, file_id)

def add_video_v3(message, file_id):
    title = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Kino", "Multfilm", "Serial", "Koreys")
    bot.send_message(message.chat.id, "📂 Janrni tanlang:", reply_markup=kb)
    bot.register_next_step_handler(message, add_video_v4, file_id, title)

def add_video_v4(message, file_id, title):
    genre = message.text
    db_cursor.execute("INSERT INTO movies (file_id, title, genre) VALUES (?, ?, ?)", (file_id, title, genre))
    db_conn.commit()
    bot.send_message(message.chat.id, f"✅ Saqlandi! ID: {db_cursor.lastrowid}", reply_markup=main_keyboard(message.from_user.id))

# ===== ADMIN: KANALNI SOZLASH =====
@bot.message_handler(func=lambda m: m.text == "📢 Kanalni sozlash" and is_admin(m.from_user.id))
def channel_set(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 Kanalni o'zgartirish", callback_data="set_ch"))
    kb.add(types.InlineKeyboardButton("❌ Obunani o'chirish", callback_data="off_ch"))
    bot.send_message(message.chat.id, f"📢 Hozirgi majburiy kanal: {get_sub_channel()}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "set_ch")
def set_ch_call(call):
    bot.send_message(call.message.chat.id, "Yangi kanal yuzernemini yuboring (masalan: @kino_olami):")
    bot.register_next_step_handler(call.message, save_channel)

def save_channel(message):
    if message.text.startswith("@"):
        db_cursor.execute("UPDATE settings SET value = ? WHERE key = 'sub_channel'", (message.text,))
        db_conn.commit()
        bot.send_message(message.chat.id, "✅ Kanal saqlandi.")
    else: bot.send_message(message.chat.id, "❌ Xato! @ bilan boshlansin.")

@bot.callback_query_handler(func=lambda c: c.data == "off_ch")
def off_ch_call(call):
    db_cursor.execute("UPDATE settings SET value = 'OFF' WHERE key = 'sub_channel'")
    db_conn.commit()
    bot.answer_callback_query(call.id, "Obuna o'chirildi", show_alert=True)

# ===== ADMINLAR QO'SHISH VA O'CHIRISH =====
@bot.message_handler(func=lambda m: m.text == "➕ Admin qo'shish" and is_admin(m.from_user.id))
def add_adm_v1(message):
    bot.send_message(message.chat.id, "Yangi admin ID raqamini yuboring:")
    bot.register_next_step_handler(message, save_adm)

def save_adm(message):
    if message.text.isdigit():
        db_cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (int(message.text),))
        db_conn.commit()
        bot.send_message(message.chat.id, "✅ Admin qo'shildi.")
    else: bot.send_message(message.chat.id, "❌ Faqat raqam yuboring.")

@bot.message_handler(func=lambda m: m.text == "➖ Admin o'chirish" and is_admin(m.from_user.id))
def rem_adm_v1(message):
    bot.send_message(message.chat.id, "O'chiriladigan admin ID sini yuboring:")
    bot.register_next_step_handler(message, del_adm)

def del_adm(message):
    if message.text.isdigit():
        uid = int(message.text)
        if uid == PRIMARY_ADMIN_ID: return bot.send_message(message.chat.id, "❌ Asosiy adminni o'chirib bo'lmaydi.")
        db_cursor.execute("DELETE FROM admins WHERE admin_id = ?", (uid,))
        db_conn.commit()
        bot.send_message(message.chat.id, "✅ Admin olib tashlandi.")

# ===== HELP TUGMASI =====
@bot.message_handler(func=lambda m: m.text == "❓ HELP")
def help_msg(message):
    text = (
        "❓ **Yordam bo'limi**\n\n"
        "🍿 **Kino ko'rish:** Kanaldan olingan kino ID raqamini botga yuboring.\n"
        "📢 **Kanalimiz:** Kinolarni @kino_olami kanalidan topishingiz mumkin.\n"
        "📥 **So'rov:** Kinoni topa olmasangiz, adminlarga so'rov yuboring."
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ===== STATISTIKA =====
@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and is_admin(m.from_user.id))
def show_stats(message):
    db_cursor.execute("SELECT COUNT(*) FROM users")
    total = db_cursor.fetchone()[0]
    db_cursor.execute("SELECT gender, COUNT(*) FROM users GROUP BY gender")
    genders = db_cursor.fetchall()
    
    res = f"📊 **Bot statistikasi:**\n\n👤 Jami a'zolar: {total} ta\n"
    for g in genders:
        res += f"🔹 {g[0]}: {g[1]} ta\n"
    
    db_cursor.execute("SELECT COUNT(*) FROM movies")
    res += f"\n🎬 Jami kinolar: {db_cursor.fetchone()[0]} ta"
    bot.send_message(message.chat.id, res, parse_mode="Markdown")

# ===== VIDEO BERISH =====
@bot.message_handler(func=lambda m: m.text.isdigit())
def send_movie(message):
    if not check_sub(message.from_user.id): return show_sub_msg(message)
    db_cursor.execute("SELECT file_id, title FROM movies WHERE id = ?", (int(message.text),))
    res = db_cursor.fetchone()
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 **Nomi:** {res[1]}\n🆔 **ID:** {message.text}")
    else: bot.send_message(message.chat.id, "❌ Bunday ID topilmadi.")

# Obuna xabari
def show_sub_msg(message):
    ch = get_sub_channel()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ A'zo bo'lish", url=f"https://t.me/{ch[1:]}"))
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub"))
    bot.send_message(message.chat.id, f"🛑 Botdan foydalanish uchun {ch} kanaliga a'zo bo'ling!", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def sub_check_callback(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Tasdiqlandi!", reply_markup=main_keyboard(call.from_user.id))
    else: bot.answer_callback_query(call.id, "❌ A'zo emassiz!", show_alert=True)

print("🚀 Bot Railway uchun tayyor!")
bot.infinity_polling()
