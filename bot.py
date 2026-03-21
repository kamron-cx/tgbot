import telebot
from telebot import types
import sqlite3

TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584

# ===== VERİTABANI BAĞLANTISI =====
def get_db_connection():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    return conn

# Veritabanı tablolarını oluşturma
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Kullanıcılar
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    # Videolar
    cursor.execute("CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT)")
    # Adminler
    cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    # Zorunlu Kanallar
    cursor.execute("CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY, channel_name TEXT)")
    
    # Ana admini ekle
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

# ===== YARDIMCI FONKSİYONLAR =====
def is_admin(uid):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (uid,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def check_subscription(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels")
    channels = cursor.fetchall()
    conn.close()
    
    not_joined = []
    for (cid,) in channels:
        try:
            status = bot.get_chat_member(cid, user_id).status
            if status not in ["creator", "administrator", "member"]:
                not_joined.append(cid)
        except:
            continue
    return not_joined

def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📋 Videolar ro‘yxati", "📤 Sorov", "❓ HELP")
    
    if is_admin(uid):
        kb.add("➕ Video qo‘shish", "🗑 Video o‘chirish")
        kb.add("👥 Foydalanuvchilar soni", "👮 Adminlar ro‘yxati")
        kb.add("📢 Reklama tarqatish", "📢 Kanal sozlamalari")
        if uid == PRIMARY_ADMIN_ID:
            kb.add("➕ Admin qo‘shish", "➖ Admin o‘chirish")
    return kb

# ===== KOMUTLAR VE MESAJLAR =====

@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()
    bot.send_message(uid, "👋 Salom! Botga xush kelibsiz.", reply_markup=main_keyboard(uid))

# --- REKLAMA TARQATISH ---
@bot.message_handler(func=lambda m: m.text == "📢 Reklama tarqatish" and is_admin(m.from_user.id))
def start_broadcast(message):
    msg = bot.send_message(message.chat.id, "📢 Reklama xabarini yuboring (Rasm, video, matn bo'lishi mumkin):")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
        except:
            continue
    bot.send_message(message.chat.id, f"✅ Reklama {count} kishiga muvaffaqiyatli yuborildi.")

# --- VİDEO İŞLEMLERİ ---
@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish" and is_admin(m.from_user.id))
def add_video_start(message):
    bot.send_message(message.chat.id, "📹 Videoni yuboring (Tavsifi bilan):")
    bot.register_next_step_handler(message, save_video_to_sql)

def save_video_to_sql(message):
    if not message.video:
        bot.send_message(message.chat.id, "❗ Faqat video yuboring.")
        return
    title = message.caption or "Nomsiz video"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO videos (file_id, title) VALUES (?, ?)", (message.video.file_id, title))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Video saqlandi! ID: {new_id}")

@bot.message_handler(func=lambda m: m.text == "📋 Videolar ro‘yxati")
def list_videos(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM videos")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "🚫 Hozircha video mavjud emas.")
        return
    
    text = "🎬 *Videolar ro'yxati:*\n\n"
    for r in rows:
        text += f"🆔 {r[0]} | {r[1]}\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- VİDEO ÇAĞIRMA (Zorunlu Abone Kontrolü) ---
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def handle_video_request(message):
    uid = message.from_user.id
    not_joined = check_subscription(uid)
    
    if not_joined:
        kb = types.InlineKeyboardMarkup()
        for cid in not_joined:
            try:
                chat = bot.get_chat(cid)
                url = f"https://t.me/{chat.username}" if chat.username else "https://t.me/telegram"
                kb.add(types.InlineKeyboardButton(f"➕ {chat.title}", url=url))
            except: continue
        kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data=f"check_{message.text}"))
        bot.send_message(uid, "❌ Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=kb)
        return

    send_video_by_id(message.chat.id, message.text)

def send_video_by_id(chat_id, vid_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, title FROM videos WHERE id = ?", (vid_id,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        bot.send_video(chat_id, res[0], caption=f"🎬 ID: {vid_id}\n📌 {res[1]}")
    else:
        bot.send_message(chat_id, "🚫 Bunday ID bilan video topilmadi.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check_callback(call):
    vid_id = call.data.split("_")[1]
    not_joined = check_subscription(call.from_user.id)
    if not not_joined:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        send_video_by_id(call.message.chat.id, vid_id)
    else:
        bot.answer_callback_query(call.id, "❌ Hali a'zo emassiz!", show_alert=True)

# --- KANAL AYARLARI ---
@bot.message_handler(func=lambda m: m.text == "📢 Kanal sozlamalari" and is_admin(m.from_user.id))
def channel_menu(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_name FROM channels")
    rows = cursor.fetchall()
    conn.close()
    
    text = "📢 *Zorunlu Kanallar:*\n\n"
    for r in rows:
        text += f"🔸 {r[1]} (`{r[0]}`)\n"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_ch"))
    kb.add(types.InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="del_ch"))
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "add_ch")
def add_ch_call(call):
    msg = bot.send_message(call.message.chat.id, "Kanal ID sini yuboring (Masalan: -100...):")
    bot.register_next_step_handler(msg, save_channel_sql)

def save_channel_sql(message):
    try:
        cid = message.text.strip()
        chat = bot.get_chat(cid)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO channels (channel_id, channel_name) VALUES (?, ?)", (cid, chat.title))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ {chat.title} qo'shildi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")

# --- ADMIN İSTATİSTİK ---
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar soni" and is_admin(m.from_user.id))
def count_users(message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    bot.send_message(message.chat.id, f"👥 Bot foydalanuvchilari: {count} ta")

# ===== BOTU BAŞLAT =====
print("🤖 SQLite Bot ishga tushdi...")
bot.infinity_polling()
