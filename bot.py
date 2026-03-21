import telebot
from telebot import types
import sqlite3
import os

# ===== SOZLAMALAR =====
TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)
PRIMARY_ADMIN_ID = 5909932584 

# ===== DATABASE SOZLASH =====
def init_db():
    conn = sqlite3.connect("kino_baza.db", check_same_thread=False)
    cursor = conn.cursor()
    # Kinolar
    cursor.execute('''CREATE TABLE IF NOT EXISTS movies (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title TEXT, genre TEXT)''')
    # Foydalanuvchilar (Jinsi va yoshi bilan)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, gender TEXT, age_range TEXT)''')
    # Adminlar
    cursor.execute('''CREATE TABLE IF NOT EXISTS admins (admin_id INTEGER PRIMARY KEY)''')
    # Majburiy kanallar
    cursor.execute('''CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT)''')
    
    cursor.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (PRIMARY_ADMIN_ID,))
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()

# ===== YORDAMCHI FUNKSIYALAR =====
def is_admin(uid: int) -> bool:
    db_cursor.execute("SELECT admin_id FROM admins WHERE admin_id = ?", (uid,))
    return db_cursor.fetchone() is not None

def check_sub(uid: int):
    db_cursor.execute("SELECT channel_id FROM channels")
    channels = db_cursor.fetchall()
    for ch in channels:
        try:
            status = bot.get_chat_member(ch[0], uid).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        except:
            continue # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa
    return True

# ===== KLAVIATURALAR =====
def main_keyboard(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📋 Kinolar ro'yxati", "📂 Janrlar bo'yicha")
    kb.row("📤 So'rov yuborish", "❓ HELP")
    
    if is_admin(uid):
        kb.row("➕ Video qo'shish", "🗑 Video o'chirish")
        kb.row("➕ Admin qo'shish", "➖ Admin o'chirish")
        kb.row("📢 Kanal qo'shish", "❌ Kanal o'chirish")
        kb.row("📊 Statistika")
    return kb

# ===== START VA RO'YXATDAN O'TISH =====
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    db_cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    user = db_cursor.fetchone()
    
    if not user:
        # Statistika uchun ma'lumot yig'ish
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("Erkak 👨", callback_data="reg_gender_Erkak"),
               types.InlineKeyboardButton("Ayol 👩", callback_data="reg_gender_Ayol"))
        bot.send_message(uid, "👋 Salom! Botdan foydalanish uchun ro'yxatdan o'ting.\n\nJinsingizni tanlang:", reply_markup=kb)
    else:
        if not check_sub(uid):
            return show_sub_msg(message)
        bot.send_message(uid, "Xush kelibsiz! Kino ID raqamini yuboring:", reply_markup=main_keyboard(uid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("reg_gender_"))
def reg_gender(call):
    gender = call.data.split("_")[2]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("18 dan kichik", callback_data=f"reg_age_{gender}_<18"),
           types.InlineKeyboardButton("18 - 30", callback_data=f"reg_age_{gender}_18-30"),
           types.InlineKeyboardButton("30 dan katta", callback_data=f"reg_age_{gender}_>30"))
    bot.edit_message_text("Yoshingizni tanlang:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("reg_age_"))
def reg_age(call):
    data = call.data.split("_")
    gender, age = data[2], data[3]
    db_cursor.execute("INSERT INTO users (user_id, gender, age_range) VALUES (?, ?, ?)", (call.from_user.id, gender, age))
    db_conn.commit()
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✅ Ro'yxatdan o'tdingiz!", reply_markup=main_keyboard(call.from_user.id))

# ===== KINOLAR RO'YXATI =====
@bot.message_handler(func=lambda m: m.text == "📋 Kinolar ro'yxati")
def movie_list(message):
    db_cursor.execute("SELECT id, title, genre FROM movies ORDER BY id DESC LIMIT 50")
    movies = db_cursor.fetchall()
    if not movies:
        return bot.send_message(message.chat.id, "Hozircha kinolar mavjud emas.")
    
    res = "🎬 **Oxirgi qo'shilgan kinolar ro'yxati:**\n\n"
    for m in movies:
        res += f"🆔 `{m[0]}` | 🎥 {m[1]} ({m[2]})\n"
    bot.send_message(message.chat.id, res, parse_mode="Markdown")

# ===== ADMIN: KANAL BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "📢 Kanal qo'shish" and is_admin(m.from_user.id))
def add_channel_start(message):
    bot.send_message(message.chat.id, "Kanal yoki guruh ID sini yuboring (Masalan: -100...):")
    bot.register_next_step_handler(message, save_channel)

def save_channel(message):
    db_cursor.execute("INSERT INTO channels (channel_id) VALUES (?)", (message.text,))
    db_conn.commit()
    bot.send_message(message.chat.id, "✅ Kanal muvaffaqiyatli qo'shildi.")

@bot.message_handler(func=lambda m: m.text == "❌ Kanal o'chirish" and is_admin(m.from_user.id))
def del_channel_start(message):
    db_cursor.execute("SELECT id, channel_id FROM channels")
    rows = db_cursor.fetchall()
    if not rows: return bot.send_message(message.chat.id, "Kanallar yo'q.")
    
    res = "O'chirmoqchi bo'lgan kanal tartib raqamini yuboring:\n\n"
    for r in rows: res += f"{r[0]}. {r[1]}\n"
    bot.send_message(message.chat.id, res)
    bot.register_next_step_handler(message, delete_channel)

def delete_channel(message):
    db_cursor.execute("DELETE FROM channels WHERE id = ?", (message.text,))
    db_conn.commit()
    bot.send_message(message.chat.id, "✅ Kanal o'chirildi.")

# ===== HELP TUGMASI =====
@bot.message_handler(func=lambda m: m.text == "❓ HELP")
def help_cmd(message):
    bot.send_message(message.chat.id, 
        "❓ **Botdan foydalanish bo'yicha qo'llanma:**\n\n"
        "1️⃣ **Kino topish:** Bizning kanalimizdan kino kodini toping va botga yuboring.\n"
        "2️⃣ **Obuna:** Bot ishlashi uchun barcha majburiy kanallarga a'zo bo'lishingiz shart.\n"
        "3️⃣ **Kino so'rash:** Agar kerakli kinoni topmasangiz, 'So'rov yuborish' tugmasi orqali adminlarga xabar qoldiring.\n\n"
        "🍿 Yoqimli tomosha!"
    )

# ===== STATISTIKA =====
@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and is_admin(m.from_user.id))
def stats(message):
    db_cursor.execute("SELECT COUNT(*) FROM users")
    total = db_cursor.fetchone()[0]
    
    db_cursor.execute("SELECT gender, COUNT(*) FROM users GROUP BY gender")
    genders = db_cursor.fetchall()
    
    db_cursor.execute("SELECT age_range, COUNT(*) FROM users GROUP BY age_range")
    ages = db_cursor.fetchall()
    
    res = f"📊 **Bot statistikasi:**\n\n👤 Jami foydalanuvchilar: {total}\n\n"
    res += " Jinsi bo'yicha:\n"
    for g in genders: res += f" - {g[0]}: {g[1]} ta\n"
    
    res += "\n Yoshi bo'yicha:\n"
    for a in ages: res += f" - {a[0]}: {a[1]} ta\n"
    
    bot.send_message(message.chat.id, res)

# ===== VIDEO OLISH =====
@bot.message_handler(func=lambda m: m.text.isdigit())
def get_movie(message):
    if not check_sub(message.from_user.id):
        return show_sub_msg(message)
    db_cursor.execute("SELECT file_id, title FROM movies WHERE id = ?", (int(message.text),))
    res = db_cursor.fetchone()
    if res:
        bot.send_video(message.chat.id, res[0], caption=f"🎬 **Nomi:** {res[1]}\n🆔 **ID:** {message.text}")
    else:
        bot.send_message(message.chat.id, "❌ Bunday ID dagi video topilmadi.")

def show_sub_msg(message):
    db_cursor.execute("SELECT channel_id FROM channels")
    rows = db_cursor.fetchall()
    kb = types.InlineKeyboardMarkup()
    for r in rows:
        try:
            link = bot.get_chat(r[0]).invite_link
            if not link: link = f"https://t.me/{str(r[0]).replace('@','')}"
            kb.add(types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=link))
        except: continue
    kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub"))
    bot.send_message(message.chat.id, "🛑 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz shart:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_callback(call):
    if check_sub(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ Rahmat! Endi botdan foydalanishingiz mumkin.", reply_markup=main_keyboard(call.from_user.id))
    else:
        bot.answer_callback_query(call.id, "❌ Hali hamma kanallarga a'zo emassiz!", show_alert=True)

# ... (Kino qo'shish va admin qo'shish funksiyalari o'zgarmasdan qoldi) ...

bot.infinity_polling()
