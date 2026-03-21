import telebot
from telebot import types
import json
import os

TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)

DB_FILE = "database.json"
PRIMARY_ADMIN_ID = 5909932584  # Sizning ID raqamingiz

# ===== DATABASE YUKLASH / SAQLASH =====
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Kerakli kalitlarni tekshirish
                keys = ["videos", "users", "admins", "requests", "channels"]
                for key in keys:
                    if key not in data: data[key] = []
                return data
        except:
            pass
    return {"videos": [], "users": [], "admins": [PRIMARY_ADMIN_ID], "requests": [], "channels": []}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

db = load_db()

# ===== YORDAMCHI FUNKSIYALAR =====
def is_admin(uid: int) -> bool:
    return uid in db["admins"]

def check_subscription(uid: int) -> bool:
    if uid == PRIMARY_ADMIN_ID: return True
    if not db.get("channels"): return True
    for ch in db["channels"]:
        try:
            member = bot.get_chat_member(ch['id'], uid)
            if member.status in ['left', 'kicked']: return False
        except: continue
    return True

# ===== KLAVIATURA (Tugmalar skrinshotdagidek) =====
def user_keyboard(uid: int) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    is_adm = is_admin(uid)
    is_primary = (uid == PRIMARY_ADMIN_ID)

    # Oddiy tugmalar
    kb.row(types.KeyboardButton("📋 Videolar ro‘yxati"))
    kb.row(types.KeyboardButton("📤 Sorov"), types.KeyboardButton("❓ HELP"))
    
    # Admin tugmalari (Emoji bilan, skrinshotdagi kabi)
    if is_adm:
        kb.row(types.KeyboardButton("➕ Video qo‘shish"), types.KeyboardButton("🗑 Video o‘chirish"))
        kb.row(types.KeyboardButton("👥 Foydalanuvchilar soni"), types.KeyboardButton("👮 Adminlar ro‘yxati"))
        kb.row(types.KeyboardButton("📋 Videolar ro‘yxati (admin)"))

    if is_primary:
        kb.row(types.KeyboardButton("📢 Kanallar"), types.KeyboardButton("➕ Kanal qo‘shish"), types.KeyboardButton("➖ Kanal o‘chirish"))
        kb.row(types.KeyboardButton("➕ Admin qo‘shish"), types.KeyboardButton("➖ Admin o‘chirish"))
        
    return kb

# ===== START =====
@bot.message_handler(commands=["start"])
def start(message: types.Message):
    uid = message.from_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()
    
    bot.send_message(uid, "👋 Salom! Bot ishga tushdi.", reply_markup=user_keyboard(uid))

# ===== MAJBURIY OBUNA BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "📢 Kanallar")
def list_ch(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    text = "📢 Kanallar:\n" + "\n".join([f"`{c['id']}`" for c in db["channels"]]) if db["channels"] else "Kanal yo'q"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish")
def add_ch(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "Kanal @username sini yuboring:")
    bot.register_next_step_handler(message, lambda m: (db["channels"].append({"id": m.text.strip()}), save_db(), bot.send_message(m.chat.id, "✅ Qo'shildi")))

@bot.message_handler(func=lambda m: m.text == "➖ Kanal o‘chirish")
def del_ch(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "O'chiriladigan kanal ID sini yuboring:")
    bot.register_next_step_handler(message, lambda m: (db.update({"channels": [c for c in db["channels"] if c['id'] != m.text.strip()]}), save_db(), bot.send_message(m.chat.id, "✅ O'chirildi")))

# ===== ADMIN BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "👮 Adminlar ro‘yxati")
def list_admins(message: types.Message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, f"👮 Adminlar ID ro'yxati:\n{db['admins']}")

@bot.message_handler(func=lambda m: m.text == "➕ Admin qo‘shish")
def add_adm(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "Yangi admin ID sini yuboring:")
    bot.register_next_step_handler(message, save_adm)

def save_adm(message: types.Message):
    try:
        new_id = int(message.text)
        if new_id not in db["admins"]:
            db["admins"].append(new_id)
            save_db()
            bot.send_message(message.chat.id, "✅ Admin qo'shildi")
    except: bot.send_message(message.chat.id, "Xato ID")

# ===== VIDEO BOSHQARUVI =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish")
def add_vid(message: types.Message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "Videoni yuboring:")
    bot.register_next_step_handler(message, save_vid)

def save_vid(message: types.Message):
    if not message.video: return
    v_id = len(db["videos"]) + 1
    db["videos"].append({"id": v_id, "file_id": message.video.file_id, "title": message.caption or "Video"})
    save_db()
    bot.send_message(message.chat.id, f"✅ Saqlandi. ID: {v_id}")

@bot.message_handler(func=lambda m: m.text == "🗑 Video o‘chirish")
def del_vid(message: types.Message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "O'chiriladigan video ID sini yuboring:")
    bot.register_next_step_handler(message, confirm_del_vid)

def confirm_del_vid(message: types.Message):
    try:
        vid = int(message.text)
        db["videos"] = [v for v in db["videos"] if v["id"] != vid]
        save_db()
        bot.send_message(message.chat.id, "✅ O'chirildi")
    except: pass

# ===== VIDEO YUBORISH (RAQAM BILAN) =====
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def send_vid(message: types.Message):
    if not check_subscription(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Kanallarga obuna bo'ling!")
        return
    vid = int(message.text)
    video = next((v for v in db["videos"] if v["id"] == vid), None)
    if video:
        bot.send_video(message.chat.id, video["file_id"], caption=f"ID: {vid}")
    else:
        bot.send_message(message.chat.id, "Topilmadi")

# ===== RUN =====
print("Bot ishlamoqda...")
bot.infinity_polling()
