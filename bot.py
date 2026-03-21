import telebot
from telebot import types
import json
import os

TOKEN = "7961600141:AAHkKdsq1bblalGv1BruRzPaBFkqb8oGnxs"
bot = telebot.TeleBot(TOKEN)

DB_FILE = "database.json"
PRIMARY_ADMIN_ID = 5909932584  # Asosiy admin ID

# ===== Ma'lumotlar bazasi funksiyalari =====
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Yangi kalitlar bo'lmasa qo'shib qo'yamiz
            if "channels" not in data: data["channels"] = []
            if "requests" not in data: data["requests"] = []
            return data
    return {"videos": [], "users": [], "admins": [PRIMARY_ADMIN_ID], "requests": [], "channels": []}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

db = load_db()

# ===== Yordamchi funksiyalar =====
def is_admin(uid: int) -> bool:
    return uid in db["admins"]

def check_subscription(uid: int) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga a'zo ekanligini tekshiradi."""
    if uid == PRIMARY_ADMIN_ID: return True # Asosiy admin tekshirilmaydi
    
    for ch in db["channels"]:
        try:
            member = bot.get_chat_member(ch['id'], uid)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            # Agar bot kanalda admin bo'lmasa yoki kanal topilmasa
            continue
    return True

def user_keyboard(uid: int) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    is_adm = is_admin(uid)
    is_primary = (uid == PRIMARY_ADMIN_ID)

    # Oddiy foydalanuvchi tugmalari
    kb.add(types.KeyboardButton("📋 Videolar ro‘yxati"))
    kb.add(types.KeyboardButton("📤 Sorov"), types.KeyboardButton("❓ HELP"))
    
    # Admin tugmalari
    if is_adm:
        kb.add(types.KeyboardButton("➕ Video qo‘shish"), types.KeyboardButton("🗑 Video o‘chirish"))
        kb.add(types.KeyboardButton("👥 Foydalanuvchilar soni"), types.KeyboardButton("👮 Adminlar ro‘yxati"))
        kb.add(types.KeyboardButton("📋 Videolar ro‘yxati (admin)"))

    # FAQAT ASOSIY ADMIN UCHUN (Majburiy obuna boshqaruvi)
    if is_primary:
        kb.add(types.KeyboardButton("📢 Kanallar"), types.KeyboardButton("➕ Kanal qo‘shish"), types.KeyboardButton("➖ Kanal o‘chirish"))
        kb.add(types.KeyboardButton("➕ Admin qo‘shish"), types.KeyboardButton("➖ Admin o‘chirish"))
        
    return kb

# ===== START KOMANDASI =====
@bot.message_handler(commands=["start"])
def start(message: types.Message):
    uid = message.from_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()
    
    text = "👋 Salom! Botimizga xush kelibsiz.\n"
    if not check_subscription(uid):
        text += "\n❗ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
        kb = types.InlineKeyboardMarkup()
        for ch in db["channels"]:
            url = f"https://t.me/{ch['id'].replace('@','')}" if str(ch['id']).startswith('@') else "https://t.me/share"
            kb.add(types.InlineKeyboardButton("Obuna bo'lish ➕", url=url))
        bot.send_message(uid, text, reply_markup=kb)
    else:
        bot.send_message(uid, text, reply_markup=user_keyboard(uid))

# ===== MAJBURIY OBUNA BOSHQARUVI (FAQAT PRIMARY ADMIN) =====
@bot.message_handler(func=lambda m: m.text == "📢 Kanallar")
def list_channels(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    if not db["channels"]:
        bot.send_message(message.chat.id, "Hozircha majburiy kanallar yo'q.")
        return
    text = "📢 Majburiy obuna kanallari:\n\n"
    for idx, ch in enumerate(db["channels"], 1):
        text += f"{idx}. `{ch['id']}`\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish")
def add_channel_prompt(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "Kanal @username sini yoki ID sini yuboring (Masalan: @kanal_nomi):")
    bot.register_next_step_handler(message, save_channel)

def save_channel(message: types.Message):
    ch_id = message.text.strip()
    if not any(c['id'] == ch_id for c in db["channels"]):
        db["channels"].append({"id": ch_id})
        save_db()
        bot.send_message(message.chat.id, f"✅ {ch_id} majburiy obunaga qo'shildi.")
    else:
        bot.send_message(message.chat.id, "❗ Bu kanal allaqachon ro'yxatda bor.")

@bot.message_handler(func=lambda m: m.text == "➖ Kanal o‘chirish")
def delete_channel_prompt(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID: return
    bot.send_message(message.chat.id, "O'chiriladigan kanal ID yoki @username sini yuboring:")
    bot.register_next_step_handler(message, remove_channel)

def remove_channel(message: types.Message):
    ch_id = message.text.strip()
    original_len = len(db["channels"])
    db["channels"] = [c for c in db["channels"] if str(c['id']) != ch_id]
    if len(db["channels"]) < original_len:
        save_db()
        bot.send_message(message.chat.id, "✅ Kanal o'chirildi.")
    else:
        bot.send_message(message.chat.id, "🚫 Bunday kanal topilmadi.")

# ===== VIDEO OLISH (RAQAM ORQALI) =====
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def get_video(message: types.Message):
    uid = message.from_user.id
    if not check_subscription(uid):
        bot.send_message(uid, "❌ Avval kanallarga a'zo bo'ling, so'ngra video ID sini yuboring!")
        return
        
    vid = int(message.text.strip())
    video = next((v for v in db["videos"] if v["id"] == vid), None)
    if not video:
        bot.send_message(message.chat.id, f"🚫 ID {vid} bo‘yicha video topilmadi.")
        return
    bot.send_video(message.chat.id, video["file_id"], caption=f"🎬 Video ID: {vid}\n📌 {video['title']}")

# ===== QOLGAN STANDART ADMIN FUNKSIYALARI (Eski kod bilan bir xil) =====

@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish")
def add_video(message: types.Message):
    if not is_admin(message.from_user.id): return
    bot.send_message(message.chat.id, "📹 Video yuboring (caption bilan):")
    bot.register_next_step_handler(message, save_video)

def save_video(message: types.Message):
    if not message.video:
        bot.send_message(message.chat.id, "❗ Bu video emas.")
        return
    new_id = len(db["videos"]) + 1
    db["videos"].append({"id": new_id, "file_id": message.video.file_id, "title": message.caption or f"Video {new_id}"})
    save_db()
    bot.send_message(message.chat.id, f"✅ Video saqlandi! ID: {new_id}")

@bot.message_handler(func=lambda m: m.text == "📋 Videolar ro‘yxati")
def list_vids(message: types.Message):
    if not db["videos"]:
        bot.send_message(message.chat.id, "🚫 Bo'sh.")
        return
    bot.send_message(message.chat.id, "🎬 ID lar: " + ", ".join([str(v['id']) for v in db["videos"]]))

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar soni")
def count_u(message: types.Message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, f"👥 Jami: {len(db['users'])} ta")

# (Admin qo'shish, o'chirish va boshqa funksiyalar kodingizda bor edi, ularni ham saqlab qoling)
# ... [Sizning eski kodingizdagi Admin boshqaruv funksiyalari] ...

# ===== /Run =====
print("🤖 Bot ishlamoqda...")
bot.infinity_polling()
