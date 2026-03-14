import telebot
from telebot import types
import json
import os

TOKEN = "8633260476:AAFlCH9VjAX5ftfd4emmxR89as661R_EccE"
bot = telebot.TeleBot(TOKEN)

DB_FILE = "database.json"
PRIMARY_ADMIN_ID = 5909932584  # Asosiy admin ID

# ===== Database yuklash / saqlash =====
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"videos": [], "users": [], "admins": [PRIMARY_ADMIN_ID], "requests": []}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

db = load_db()

# ===== Foydali funksiyalar =====
def is_admin(uid: int) -> bool:
    return uid in db["admins"]

def user_keyboard(is_admin_flag: bool) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Oddiy foydalanuvchi tugmalari
    kb.add(types.KeyboardButton("📋 Videolar ro‘yxati"))
    kb.add(types.KeyboardButton("📤 Sorov"))
    kb.add(types.KeyboardButton("❓ HELP"))
    # Admin tugmalari
    if is_admin_flag:
        kb.add(types.KeyboardButton("➕ Video qo‘shish"), types.KeyboardButton("🗑 Video o‘chirish"))
        kb.add(types.KeyboardButton("👥 Foydalanuvchilar soni"), types.KeyboardButton("👮 Adminlar ro‘yxati"))
        kb.add(types.KeyboardButton("➕ Admin qo‘shish"), types.KeyboardButton("➖ Admin o‘chirish"))
        kb.add(types.KeyboardButton("📋 Videolar ro‘yxati (admin)"))
    return kb

# ===== /start =====
@bot.message_handler(commands=["start"])
def start(message: types.Message):
    uid = message.from_user.id
    if uid not in db["users"]:
        db["users"].append(uid)
        save_db()
    bot.send_message(uid, "👋 Salom! Xush kelibsiz.", reply_markup=user_keyboard(is_admin(uid)))

# ===== HELP =====
@bot.message_handler(func=lambda m: m.text == "❓ HELP")
def help_cmd(message: types.Message):
    bot.send_message(message.chat.id,
        "ℹ️ Botdan foydalanish bo‘yicha yordam:\n\n"
        "- Raqam yuboring (1, 2, 3 ...) → video olasiz\n"
        "- 📋 Videolar ro‘yxati → mavjud videolar ID sini ko‘rasiz\n"
        "- 📤 Sorov → adminlarga yozishingiz mumkin"
    )

# ===== Videolar ro‘yxati (foydalanuvchi) =====
@bot.message_handler(func=lambda m: m.text == "📋 Videolar ro‘yxati")
def videos_list(message: types.Message):
    if not db["videos"]:
        bot.send_message(message.chat.id, "🚫 Hozircha video mavjud emas.")
        return
    lines = ["🎬 Videolar ro‘yxati:"]
    for v in db["videos"]:
        lines.append(f"ID: {v['id']}")
    bot.send_message(message.chat.id, "\n".join(lines))

# ===== Videolar ro‘yxati (admin) =====
@bot.message_handler(func=lambda m: m.text == "📋 Videolar ro‘yxati (admin)")
def videos_list_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    if not db["videos"]:
        bot.send_message(message.chat.id, "🚫 Hozircha video yo‘q.")
        return
    lines = ["🎬 Videolar ro‘yxati (admin):"]
    for v in db["videos"]:
        lines.append(f"ID: {v['id']} | {v['title']}")
    bot.send_message(message.chat.id, "\n".join(lines))

# ===== Video qo‘shish =====
@bot.message_handler(func=lambda m: m.text == "➕ Video qo‘shish")
def add_video(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(message.chat.id, "📹 Menga video yuboring (caption bilan).")
    bot.register_next_step_handler(message, save_video)

def save_video(message: types.Message):
    if not message.video:
        bot.send_message(message.chat.id, "❗ Faqat video yuboring.")
        return
    new_id = len(db["videos"]) + 1
    db["videos"].append({
        "id": new_id,
        "file_id": message.video.file_id,
        "title": message.caption or f"Video {new_id}"
    })
    save_db()
    bot.send_message(message.chat.id, f"✅ Video saqlandi! ID: {new_id}")

# ===== Video o‘chirish =====
@bot.message_handler(func=lambda m: m.text == "🗑 Video o‘chirish")
def delete_video(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(message.chat.id, "🗑 Qaysi ID dagi videoni o‘chirmoqchisiz?")
    bot.register_next_step_handler(message, confirm_delete)

def confirm_delete(message: types.Message):
    try:
        vid = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "❗ Raqam yuboring.")
        return
    video = next((v for v in db["videos"] if v["id"] == vid), None)
    if not video:
        bot.send_message(message.chat.id, "🚫 Bunday video mavjud emas.")
        return
    db["videos"].remove(video)
    save_db()
    bot.send_message(message.chat.id, f"✅ ID {vid} dagi video o‘chirildi.")

# ===== Video olish (raqam orqali) =====
@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def get_video_by_number(message: types.Message):
    vid = int(message.text.strip())
    video = next((v for v in db["videos"] if v["id"] == vid), None)
    if not video:
        bot.send_message(message.chat.id, f"🚫 ID {vid} bo‘yicha video mavjud emas.")
        return
    bot.send_video(message.chat.id, video["file_id"],
                   caption=f"🎬 Video ID: {vid}\n📌 Nomi: {video['title']}")

# ===== Sorov =====
@bot.message_handler(func=lambda m: m.text == "📤 Sorov")
def request_start(message: types.Message):
    bot.send_message(message.chat.id, "📩 Xabaringizni yuboring (matn yoki media).")
    bot.register_next_step_handler(message, save_request)

def save_request(message: types.Message):
    req = {"user_id": message.from_user.id, "text": message.text or "", "mid": message.message_id}
    db["requests"].append(req)
    save_db()
    bot.send_message(message.chat.id, "✅ Sorovingiz yuborildi. Adminlar tez orada javob berishadi.")
    # Adminlarga yuboramiz
    for aid in db["admins"]:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✍️ Javob yozish", callback_data=f"reply_{message.from_user.id}"))
        bot.send_message(aid, f"📥 Yangi sorov!\n👤 User ID: `{message.from_user.id}`\n💬 {req['text']}",
                         parse_mode="Markdown", reply_markup=kb)

# ===== Admin javobi =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("reply_"))
def reply_button(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    target_id = int(call.data.split("_")[1])
    bot.send_message(call.message.chat.id, f"✍️ Javob matnini yuboring (foydalanuvchi ID: {target_id}).")
    bot.register_next_step_handler(call.message, lambda m: send_admin_reply(m, target_id))

def send_admin_reply(message: types.Message, target_id: int):
    try:
        bot.send_message(target_id, f"📩 *Admin javobi:*\n{message.text}", parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ Javob yuborildi.")
    except:
        bot.send_message(message.chat.id, "⚠️ Foydalanuvchiga javob yuborib bo‘lmadi (u botni bloklagan bo‘lishi mumkin).")

# ===== Admin qo‘shish =====
@bot.message_handler(func=lambda m: m.text == "➕ Admin qo‘shish")
def add_admin(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Yangi admin ID sini yuboring:")
    bot.register_next_step_handler(message, save_admin)

def save_admin(message: types.Message):
    try:
        uid = int(message.text.strip())
        if uid not in db["admins"]:
            db["admins"].append(uid)
            save_db()
            bot.send_message(message.chat.id, f"✅ {uid} admin qilindi.")
        else:
            bot.send_message(message.chat.id, "❗ Bu foydalanuvchi allaqachon admin.")
    except:
        bot.send_message(message.chat.id, "❗ Noto‘g‘ri ID.")

# ===== Admin o‘chirish =====
@bot.message_handler(func=lambda m: m.text == "➖ Admin o‘chirish")
def remove_admin(message: types.Message):
    if message.from_user.id != PRIMARY_ADMIN_ID:
        return
    bot.send_message(message.chat.id, "O‘chiriladigan admin ID sini yuboring:")
    bot.register_next_step_handler(message, confirm_remove_admin)

def confirm_remove_admin(message: types.Message):
    try:
        uid = int(message.text.strip())
        if uid == PRIMARY_ADMIN_ID:
            bot.send_message(message.chat.id, "❗ Asosiy adminni o‘chirib bo‘lmaydi.")
            return
        if uid in db["admins"]:
            db["admins"].remove(uid)
            save_db()
            bot.send_message(message.chat.id, f"✅ {uid} adminlikdan olindi.")
        else:
            bot.send_message(message.chat.id, "🚫 Bunday admin yo‘q.")
    except:
        bot.send_message(message.chat.id, "❗ Noto‘g‘ri ID.")

# ===== Foydalanuvchilar soni =====
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar soni")
def users_count(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    bot.send_message(message.chat.id, f"👥 Jami foydalanuvchilar: {len(db['users'])}")

# ===== Adminlar ro‘yxati =====
@bot.message_handler(func=lambda m: m.text == "👮 Adminlar ro‘yxati")
def show_admins(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    if not db["admins"]:
        bot.send_message(message.chat.id, "🚫 Hozircha adminlar yo‘q.")
        return

    lines = ["👮 Adminlar ro‘yxati:"]
    for idx, uid in enumerate(db["admins"], start=1):
        try:
            user = bot.get_chat(uid)
            name = f"@{user.username}" if user.username else user.first_name
        except:
            name = "❓ Noma'lum"
        mark = "⭐ Asosiy admin" if uid == PRIMARY_ADMIN_ID else ""
        lines.append(f"{idx}. {name} (ID: {uid}) {mark}")

    bot.send_message(message.chat.id, "\n".join(lines))

# ===== Run bot =====
print("🤖 Bot ishga tushdi...")
bot.infinity_polling()