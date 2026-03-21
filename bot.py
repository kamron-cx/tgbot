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
    kb.row("Videolar ruyxati")
    kb.row("Sorov", "HELP")
    if is_admin(uid):
        kb.row("Video qushish", "Video uchirish")
        kb.row("Foydalanuvchilar soni", "Adminlar ruyxati")
        kb.row("Reklama tarqatish")
    if uid == PRIMARY_ADMIN_ID:
        kb.row("Kanallar", "Kanal qushish", "Kanal uchirish")
        kb.row("Admin qushish", "Admin uchirish")
    return kb

# ===== KOMANDALAR =====
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    db_query('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (uid,), commit=True)
    bot.send_message(uid, "Salom! Bot ishga tushdi.", reply_markup=get_kb(uid))

# ===== REKLAMA TARQATISH =====
@bot.message_handler(func=lambda m: m.text == "Reklama tarqatish")
def start_broadcast(message):
    if not is_admin(message.from_user.id): return
    msg = bot.send_message(message.chat.id, "Reklama xabarini yuboring. Bekor qilish uchun /cancel yuboring.")
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "Reklama bekor qilindi.")
        return
    users = db_query('SELECT user_id FROM users', fetchall=True)
    count, error_count = 0, 0
    status_msg = bot.send_message(message.chat.id, "Tarqatish boshlandi...")
    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
        except:
            error_count += 1
            continue
    bot.send_message(message.chat.id, f"Yakunlandi!\nYetkazildi: {count}\nBloklaganlar: {error_count}")

# ===== VIDEO VA KANAL BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "Video qushish")
def add_v(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "Videoni yuboring:")
    bot.register_next_step_handler(message, save_v)

def save_v(message):
    if not message.video:
        bot.send_message(message.chat.id, "Xato: Bu video emas.")
        return
    db_query('INSERT INTO videos (file_id, title) VALUES (?, ?)', (message.video.file_id, message.caption or "Video"), commit=True)
    bot.send_message(message.chat.id, "Video saqlandi.")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def send_v(message):
    if not check_sub(message.from_user.id):
        channels = db_query('SELECT ch_id FROM channels', fetchall=True)
        kb = types.InlineKeyboardMarkup()
        for (ch,) in channels:
            url = f"https://t.me/{ch.replace('@','')}"
            kb.add(types.InlineKeyboardButton("Obuna bulish", url=url))
        bot.send_message(message.chat.id, "Botdan foydalanish uchun kanallarga obuna buling:", reply_markup=kb)
        return
    res = db_query('SELECT file_id, title FROM videos WHERE id=?', (message.text,), fetchone=True)
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"Nomi: {res[1]}\nID: {message.text}")
    else:
        bot.send_message(message.chat.id, "Bunday ID dagi video topilmadi.")

# ===== ADMIN VA KANAL BOSHQARUVI QOLGAN QISMI =====
@bot.message_handler(func=lambda m: m.text == "Foydalanuvchilar soni")
def stats(message):
    if is_admin(message.from_user.id):
        count = db_query('SELECT COUNT(*) FROM users', fetchone=True)[0]
        bot.send_message(message.chat.id, f"Jami foydalanuvchilar: {count}")

@bot.message_handler(func=lambda m: m.text == "Kanal qushish")
def add_ch_start(message):
    if message.from_user.id == PRIMARY_ADMIN_ID:
        bot.send_message(message.chat.id, "Kanal @username sini yuboring:")
        bot.register_next_step_handler(message, save_ch)

def save_ch(message):
    db_query('INSERT OR IGNORE INTO channels (ch_id) VALUES (?)', (message.text.strip(),), commit=True)
    bot.send_message(message.chat.id, "Kanal saqlandi.")

@bot.message_handler(func=lambda m: m.text == "Kanallar")
def list_ch(message):
    if message.from_user.id == PRIMARY_ADMIN_ID:
        chs = db_query('SELECT ch_id FROM channels', fetchall=True)
        text = "Majburiy kanallar:\n" + "\n".join([c[0] for c in chs]) if chs else "Ro'yxat bo'sh"
        bot.send_message(message.chat.id, text)

# RUN
print("Bot ishga tushdi...")
bot.infinity_polling()

