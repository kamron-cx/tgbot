import telebot
from telebot import types
import sqlite3
import time

TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)

PRIMARY_ADMIN_ID = 5909932584 
MOVIE_CHANNEL_ID = -1003897276958 

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
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("sub_channel", "@kino_olami"))
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()
db_cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
db_conn.commit()

# ===== Yordamchi funksiyalar =====
def get_sub_channel():
    db_cursor.execute("SELECT value FROM settings WHERE key = 'sub_channel'")
    res = db_cursor.fetchone()
    return res[0] if res else None

def is_admin(uid: int) -> bool:
    db_cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (uid,))
    return db_cursor.fetchone() is not None

def check_sub(uid: int):
    channel = get_sub_channel()
    if not channel: return True
    try:
        status = bot.get_chat_member(channel, uid).status
        return status in ['member', 'administrator', 'creator']
    except:
        return True

def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("🎬 Barcha kinolar"), types.KeyboardButton("📂 Janrlar bo'yicha"))
    kb.add(types.KeyboardButton("📤 Kino so'rash"), types.KeyboardButton("❓ Yordam"))
    if is_admin(uid):
        kb.add(types.KeyboardButton("➕ Kino qo'shish"), types.KeyboardButton("📢 Reklama tarqatish"))
        kb.add(types.KeyboardButton("📊 Statistika"), types.KeyboardButton("⚙️ Sozlamalar"))
    return kb

# ===== Admin: Kanal sozlamalari =====
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

# ===== Majburiy obuna tekshiruvi =====
@bot.message_handler(func=lambda m: not check_sub(m.from_user.id))
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
        bot.send_message(call.message.chat.id, "🎉 **Rahmat!** Kirish ruxsat etildi. Kino ID raqamini yuboring yoki menyudan foydalaning.", 
                         reply_markup=main_keyboard(call.from_user.id))
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo emassiz!", show_alert=True)

# ===== Start =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    db_cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    db_conn.commit()
    bot.send_message(uid, "👋 **Assalomu alaykum!**\n\nKino botimizga xush kelibsiz. Bu yerda siz eng sara kinolarni topishingiz mumkin! 🍿", 
                     reply_markup=main_keyboard(uid), parse_mode="Markdown")

# ===== 5-funksiya: Reklama =====
@bot.message_handler(func=lambda m: m.text == "📢 Reklama tarqatish")
def promo_start(message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "📝 **Reklama xabarini yuboring:**\n(Matn, rasm yoki video bo'lishi mumkin)")
    bot.register_next_step_handler(message, send_promo)

def send_promo(message):
    db_cursor.execute("SELECT user_id FROM users")
    users = db_cursor.fetchall()
    bot.send_message(message.chat.id, f"🚀 **Tarqatish boshlandi...**")
    count = 0
    for user in users:
        try:
            bot.copy_message(user[0], message.chat.id, message.message_id)
            count += 1
            time.sleep(0.05)
        except: continue
    bot.send_message(message.chat.id, f"🏁 **Tayyor!**\n✅ {count} ta foydalanuvchiga xabar yetkazildi.")

# ===== 4-funksiya: Janrlar =====
@bot.message_handler(func=lambda m: m.text == "📂 Janrlar bo'yicha")
def genres_list(message):
    kb = types.InlineKeyboardMarkup()
    genres = [("💥 Boevik", "Kino"), ("🦁 Multfilm", "Multfilm"), ("📺 Serial", "Serial"), ("🎎 Koreys", "Koreys")]
    for text, data in genres:
        kb.add(types.InlineKeyboardButton(text, callback_data=f"genre_{data}"))
    bot.send_message(message.chat.id, "📂 **Kategoriyani tanlang:**", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("genre_"))
def show_by_genre(call):
    genre = call.data.split("_")[1]
    db_cursor.execute("SELECT id, title FROM movies WHERE genre = ?", (genre,))
    rows = db_cursor.fetchall()
    if not rows:
        bot.answer_callback_query(call.id, "😕 Bu bo'limda hozircha kinolar yo'q.")
        return
    res = f"🗂 **{genre} bo'limidagi kinolar:**\n\n" + "\n".join([f"🔹 `{r[0]}`. {r[1]}" for r in rows])
    bot.send_message(call.message.chat.id, res, parse_mode="Markdown")

# ===== Statistika =====
@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def stats(message):
    if not is_admin(message.from_user.id): return
    db_cursor.execute("SELECT COUNT(*) FROM users")
    u_count = db_cursor.fetchone()[0]
    db_cursor.execute("SELECT COUNT(*) FROM movies")
    m_count = db_cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"📊 **Bot statistikasi:**\n\n👤 Foydalanuvchilar: `{u_count}`\n🎬 Jami kinolar: `{m_count}`", parse_mode="Markdown")

# ===== ID orqali video olish =====
@bot.message_handler(func=lambda m: m.text.isdigit())
def get_movie(message):
    db_cursor.execute("SELECT file_id, title FROM movies WHERE id = ?", (int(message.text),))
    res = db_cursor.fetchone()
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 **Nomi:** {res[1]}\n\n✅ @SizningKanaliz", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "🚫 **Kino topilmadi!**\nID raqami noto'g'ri kiritilgan bo'lishi mumkin.")

print("🚀 Bot chiroyli dizaynda ishga tushdi!")
bot.infinity_polling()
