import telebot
from telebot import types
import sqlite3
import time

# ===== SOZLAMALAR =====
TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584 

# ===== DATABASE SOZLASH =====
def init_db():
    conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
    cursor = conn.cursor()
    # Videolar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       file_id TEXT, title TEXT, genre TEXT)''')
    # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    # Adminlar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)''')
    # Sozlamalar (Kanal va h.k)
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Birlamchi ma'lumotlar
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
    kb.row("📋 Videolar ro'yxati", "📂 Janrlar bo'yicha")
    kb.row("📤 So'rov yuborish", "❓ HELP")
    
    if is_admin(uid):
        kb.row("➕ Video qo'shish", "🗑 Video o'chirish")
        kb.row("👥 Foydalanuvchilar", "👮 Adminlar boshqaruvi")
        kb.row("📊 Statistika", "⚙️ Sozlamalar")
    return kb

# ===== START VA OBUNA =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    db_cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    db_conn.commit()
    
    if not check_sub(uid):
        return show_sub_msg(message)
    
    bot.send_message(uid, "👋 Salom! Botga xush kelibsiz.\nKino ID raqamini yuboring yoki menyudan foydalaning.", 
                     reply_markup=main_keyboard(uid))

def show_sub_msg(message):
    channel = get_sub_channel()
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ A'zo bo'lish", url=f"https://t.me/{channel[1:]}"))
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub"))
    bot.send_message(message.chat.id, f"🛑 Botdan foydalanish uchun {channel} kanaliga a'zo bo'lishingiz shart!", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_callback(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Rahmat! Botdan foydalanishingiz mumkin.", reply_markup=main_keyboard(call.from_user.id))
    else:
        bot.answer_callback_query(call.id, "❌ Hali a'zo emassiz!", show_alert=True)

# ===== ADMIN: VIDEO QO'SHISH =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo'shish" and is_admin(m.from_user.id))
def add_video_step1(message):
    bot.send_message(message.chat.id, "📹 Videoni yuboring:")
    bot.register_next_step_handler(message, add_video_step2)

def add_video_step2(message):
    if not message.video:
        return bot.send_message(message.chat.id, "❌ Faqat video yuboring!")
    file_id = message.video.file_id
    bot.send_message(message.chat.id, "📝 Video nomini (caption) yuboring:")
    bot.register_next_step_handler(message, add_video_step3, file_id)

def add_video_step3(message, file_id):
    title = message.text
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Kino", "Multfilm", "Serial", "Koreys")
    bot.send_message(message.chat.id, "📂 Janrni tanlang:", reply_markup=kb)
    bot.register_next_step_handler(message, add_video_final, file_id, title)

def add_video_final(message, file_id, title):
    genre = message.text
    db_cursor.execute("INSERT INTO movies (file_id, title, genre) VALUES (?, ?, ?)", (file_id, title, genre))
    db_conn.commit()
    new_id = db_cursor.lastrowid
    bot.send_message(message.chat.id, f"✅ Saqlandi! ID: {new_id}", reply_markup=main_keyboard(message.from_user.id))

# ===== ADMIN: ADMINLAR BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "👮 Adminlar boshqaruvi" and is_admin(m.from_user.id))
def admin_manage(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_adm"))
    kb.add(types.InlineKeyboardButton("➖ Admin o'chirish", callback_data="rem_adm"))
    kb.add(types.InlineKeyboardButton("📋 Ro'yxat", callback_data="list_adm"))
    bot.send_message(message.chat.id, "👮 Adminlarni boshqarish menyusi:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "add_adm")
def add_adm_call(call):
    if call.from_user.id != PRIMARY_ADMIN_ID:
        return bot.answer_callback_query(call.id, "Faqat asosiy admin qo'sha oladi!", show_alert=True)
    bot.send_message(call.message.chat.id, "Yangi admin ID raqamini yuboring:")
    bot.register_next_step_handler(call.message, save_new_admin)

def save_new_admin(message):
    if message.text.isdigit():
        new_id = int(message.text)
        db_cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (new_id,))
        db_conn.commit()
        bot.send_message(message.chat.id, f"✅ {new_id} admin qilib tayinlandi.")
    else:
        bot.send_message(message.chat.id, "❌ Faqat raqam yuboring.")

# ===== SO'ROV VA JAVOB =====
@bot.message_handler(func=lambda m: m.text == "📤 So'rov yuborish")
def ask_request(message):
    bot.send_message(message.chat.id, "📩 Adminlarga xabaringizni yuboring:")
    bot.register_next_step_handler(message, forward_to_admins)

def forward_to_admins(message):
    db_cursor.execute("SELECT admin_id FROM admins")
    admins = db_cursor.fetchall()
    for adm in admins:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✍️ Javob berish", callback_data=f"ans_{message.from_user.id}"))
        bot.send_message(adm[0], f"📥 **Yangi so'rov!**\n👤 Kimdan: {message.from_user.id}\n💬 Xabar: {message.text}", 
                         reply_markup=kb, parse_mode="Markdown")
    bot.send_message(message.chat.id, "✅ Xabaringiz yuborildi.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("ans_"))
def answer_call(call):
    target_id = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, f"✍️ {target_id} uchun javobingizni yozing:")
    bot.register_next_step_handler(call.message, send_answer_to_user, target_id)

def send_answer_to_user(message, target_id):
    try:
        bot.send_message(target_id, f"📩 **Admin javobi:**\n{message.text}", parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ Javob yuborildi.")
    except:
        bot.send_message(message.chat.id, "❌ Xabar yuborilmadi (User botni bloklagan).")

# ===== VIDEO OLISH (ID ORQALI) =====
@bot.message_handler(func=lambda m: m.text.isdigit())
def get_movie(message):
    if not check_sub(message.from_user.id): return show_sub_msg(message)
    db_cursor.execute("SELECT file_id, title FROM movies WHERE id = ?", (int(message.text),))
    res = db_cursor.fetchone()
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 **Nomi:** {res[1]}\n🆔 **ID:** {message.text}")
    else:
        bot.send_message(message.chat.id, "❌ Bunday ID dagi video topilmadi.")

# ===== STATISTIKA =====
@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and is_admin(m.from_user.id))
def show_stats(message):
    db_cursor.execute("SELECT COUNT(*) FROM users")
    u_count = db_cursor.fetchone()[0]
    db_cursor.execute("SELECT COUNT(*) FROM movies")
    m_count = db_cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"📊 **Statistika:**\n👤 Foydalanuvchilar: {u_count}\n🎬 Kinolar: {m_count}", parse_mode="Markdown")

# ===== BOTNI ISHGA TUSHIRISH =====
print("🚀 Bot ishga tushdi...")
bot.infinity_polling()
