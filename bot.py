import datetime
import threading
import time
import pytz
import telebot
from telebot import types

# --- Configuration & Credentials ---
API_TOKEN = "8683150922:AAFBcqOyG6YugrzfL6u3nRmu9zz9yJwqiDc"
MASTER_PASSWORD = "4071041"
ADMINS = ["alamin_041", "aminal041"]
BACKUP_GROUP_ID = -1003210815541  # Group ID extracted from topic links

# Topic Message Thread IDs
TOPIC_LOGIN = 2
TOPIC_SUPPORT = 5
TOPIC_FORGOT = 6

bot = telebot.TeleBot(API_TOKEN)

# --- In-Memory Database (Production এ SQLite/MongoDB ব্যবহার করতে পারেন) ---
# users[chat_id] = {roll, name, category, password, status, status_note, exam_subject, exam_date, exam_time}
users_db = {}
roll_counter = 10001
pending_registrations = {}  # chat_id -> state data
active_chats = {}  # admin_chat_id <-> user_chat_id


# --- Time Utilities ---
def get_live_times():
    bd_tz = pytz.timezone("Asia/Dhaka")
    ru_tz = pytz.timezone("Europe/Moscow")
    now_utc = datetime.datetime.now(pytz.utc)

    bd_time = now_utc.astimezone(bd_tz).strftime("%d %B %Y, %I:%M %p")
    ru_time = now_utc.astimezone(ru_tz).strftime("%d %B %Y, %I:%M %p")
    return bd_time, ru_time


# --- Middleware / Security Decorator ---
def is_admin(username):
    if not username:
        return False
    return username.lower() in [a.lower() for a in ADMINS]


# --- /start Command & Lock System ---
@bot.message_handler(commands=["start"])
def start_bot(message):
    chat_id = message.chat.id
    bd, ru = get_live_times()

    welcome_text = (
        f"🤖 *Edu: Journey Help Bot*\n\n"
        f"🇧🇩 BD Time: `{bd}`\n"
        f"🇷🇺 RU Time: `{ru}`\n\n"
        f"🔒 বটটি বর্তমানে লক করা আছে। ব্যবহারের জন্য অনুগ্রহ করে মাস্টার পাসওয়ার্ড দিন:"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔑 পাসওয়ার্ড দিন", callback_data="enter_pass"),
        types.InlineKeyboardButton(
            "💬 সাহায্য / সাপোর্ট", callback_data="support_start"
        ),
    )
    bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "enter_pass")
def ask_password(call):
    msg = bot.send_message(
        call.message.chat.id, "দয়া করে পাসওয়ার্ডটি টাইপ করে পাঠান:"
    )
    bot.register_next_step_handler(msg, verify_master_password)


def verify_master_password(message):
    chat_id = message.chat.id
    if message.text.strip() == MASTER_PASSWORD:
        # Check if already registered
        if chat_id in users_db:
            main_menu(chat_id, "স্বাগতম! আপনার বট ইতিমধ্যে আনলক করা আছে।")
        else:
            # Start Registration Flow
            pending_registrations[chat_id] = {}
            msg = bot.send_message(
                chat_id,
                "✅ পাসওয়ার্ড সঠিক!\n\nআপনার পূর্ণাঙ্গ নামটি (Full Name) লিখে পাঠান:",
            )
            bot.register_next_step_handler(msg, process_user_name)
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🔄 পুনরায় চেষ্টা করুন", callback_data="enter_pass"),
            types.InlineKeyboardButton("❓ পাসওয়ার্ড ভুলে গেছেন?", callback_data="forgot_pass")
        )
        bot.send_message(chat_id, "❌ ভুল পাসওয়ার্ড দিয়েছেন!", reply_markup=markup)


# --- Registration Flow ---
def process_user_name(message):
    chat_id = message.chat.id
    pending_registrations[chat_id]["name"] = message.text.strip()

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Self Fund", callback_data="cat_self"),
        types.InlineKeyboardButton("Scholarship", callback_data="cat_sch"),
    )
    bot.send_message(
        chat_id, "আপনার ক্যাটেগরি সিলেক্ট করুন:", reply_markup=markup
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ["cat_self", "cat_sch"]
)
def process_category(call):
    chat_id = call.message.chat.id
    category = "Self Fund" if call.data == "cat_self" else "Scholarship"
    pending_registrations[chat_id]["category"] = category

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🤖 অটো জেনারেট পাসওয়ার্ড", callback_data="pass_auto"),
        types.InlineKeyboardButton("✍️ নিজের পছন্দমতো পাসওয়ার্ড", callback_data="pass_custom")
    )
    bot.edit_message_text(
        "আপনার ব্যক্তিগত পাসওয়ার্ড সেট করার পদ্ধতি বেছে নিন:",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ["pass_auto", "pass_custom"]
)
def process_pass_choice(call):
    chat_id = call.message.chat.id
    if call.data == "pass_auto":
        import random
        password = str(random.randint(100000, 999999))
        finalize_registration(chat_id, password, call.message)
    else:
        msg = bot.send_message(chat_id, "আপনার পছন্দমতো পাসওয়ার্ডটি লিখে পাঠান:")
        bot.register_next_step_handler(msg, process_custom_password_step)


def process_custom_password_step(message):
    finalize_registration(message.chat.id, message.text.strip(), message)


def finalize_registration(chat_id, user_pass, message_obj):
    global roll_counter
    roll = roll_counter
    roll_counter += 1

    data = pending_registrations.get(chat_id, {})
    name = data.get("name", "Unknown")
    category = data.get("category", "General")
    username = message_obj.from_user.username or "No Username"

    # Save to DB
    users_db[chat_id] = {
        "roll": roll,
        "name": name,
        "category": category,
        "password": user_pass,
        "status": "There are no updates",
        "status_note": "রেজিস্ট্রেশন সফল হয়েছে।",
        "exam_subject": "Not Set",
        "exam_date": "Not Set",
        "exam_time": "Not Set",
    }

    # Forward to Login Topic
    log_text = (
        f"📥 *New User Registration*\n"
        f"🆔 Roll: `{roll}`\n"
        f"👤 Name: {name}\n"
        f"🏷️ Category: {category}\n"
        f"🔑 User Password: `{user_pass}`\n"
        f"🔗 Telegram: @{username} (ID: `{chat_id}`)"
    )
    bot.send_message(
        BACKUP_GROUP_ID, log_text, parse_mode="Markdown", message_thread_id=TOPIC_LOGIN
    )

    success_msg = (
        f"🎉 অভিনন্দন! আপনার রেজিস্ট্রেশন সফল হয়েছে।\n\n"
        f"📌 আপনার রোল নম্বর: `{roll}`\n"
        f"🔑 আপনার পাসওয়ার্ড: `{user_pass}`\n"
        f"(এই তথ্যগুলো নিরাপদে রাখুন)"
    )
    bot.send_message(chat_id, success_msg, parse_mode="Markdown")
    main_menu(chat_id, "প্রধান মেনুতে স্বাগতম:")


# --- Forgot Password Handler ---
@bot.callback_query_handler(func=lambda call: call.data == "forgot_pass")
def forgot_password_start(call):
    msg = bot.send_message(
        call.message.chat.id, "আপনার **রোল নম্বর** বা **নাম** লিখে পাঠান যাতে এডমিন চিনতে পারেন:"
    )
    bot.register_next_step_handler(msg, process_forgot_password)


def process_forgot_password(message):
    chat_id = message.chat.id
    text = message.text.strip()
    username = message.from_user.username or "No Username"

    forward_text = (
        f"🔄 *Forgot Password Request*\n"
        f"👤 Name/Details: {text}\n"
        f"🔗 Telegram: @{username} (ID: `{chat_id}`)"
    )
    bot.send_message(
        BACKUP_GROUP_ID,
        forward_text,
        parse_mode="Markdown",
        message_thread_id=TOPIC_FORGOT,
    )
    bot.send_message(
        chat_id,
        "✅ আপনার পাসওয়ার্ড রিকোয়েস্টটি এডমিনের কাছে পাঠানো হয়েছে। খুব শীঘ্রই আপনাকে জানানো হবে।",
    )


# --- Main Menu ---
def main_menu(chat_id, text_note):
    bd, ru = get_live_times()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 স্ট্যাটাস ও শিডিউল চেক", callback_data="check_status"),
        types.InlineKeyboardButton("📁 ডকুমেন্টস গাইড", callback_data="docs_guide"),
        types.InlineKeyboardButton("💬 সাহায্য (Support)", callback_data="support_start"),
    )
    if is_admin(bot.get_chat(chat_id).username):  # Simple check, or maintain admin list
        markup.add(types.InlineKeyboardButton("🛠️ এডমিন প্যানেল", callback_data="admin_panel"))

    menu_text = (
        f"{text_note}\n\n"
        f"🇧🇩 BD Time: `{bd}`\n"
        f"🇷🇺 RU Time: `{ru}`"
    )
    bot.send_message(chat_id, menu_text, parse_mode="Markdown", reply_markup=markup)


# --- Status & Exam Schedule Check ---
@bot.callback_query_handler(func=lambda call: call.data == "check_status")
def prompt_roll_for_status(call):
    msg = bot.send_message(
        call.message.chat.id, "আপনার **রোল নম্বর** (যেমন: 10001) লিখে পাঠান:"
    )
    bot.register_next_step_handler(msg, show_user_status_result)


def show_user_status_result(message):
    chat_id = message.chat.id
    try:
        roll = int(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ সঠিক রোল নম্বর দিন (শুধু সংখ্যা)।")
        return

    # Find user by roll
    target_user = None
    for u_id, u_data in users_db.items():
        if u_data["roll"] == roll:
            target_user = u_data
            break

    if target_user:
        res_text = (
            f"📋 *Roll No: {target_user['roll']}*\n"
            f"👤 Name: {target_user['name']}\n"
            f"📌 Status: *{target_user['status']}*\n"
            f"📝 Note: {target_user['status_note']}\n\n"
            f"📚 Exam Subject: {target_user['exam_subject']}\n"
            f"📅 Exam Date: {target_user['exam_date']}\n"
            f"⏰ Exam Time: {target_user['exam_time']}"
        )
        bot.send_message(chat_id, res_text, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "❌ এই রোল নম্বরের কোনো ডাটা পাওয়া যায়নি।")


# --- Document Guide Menu ---
@bot.callback_query_handler(func=lambda call: call.data == "docs_guide")
def docs_guide_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🇷🇺 রাশিয়া Self fund", callback_data="doc_self"),
        types.InlineKeyboardButton("🇷🇺 Russia Scholarship", callback_data="doc_russia_sch"),
        types.InlineKeyboardButton("🏛️ Embassy Document - Scholarship", callback_data="doc_embassy"),
        types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="back_to_menu")
    )
    bot.edit_message_text(
        "কোন ক্যাটেগরির ডকুমেন্টস দেখতে চান সিলেক্ট করুন:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
    )


@bot.callback_query_handler(
    func=lambda call: call.data in ["doc_self", "doc_russia_sch", "doc_embassy", "back_to_menu"]
)
def handle_doc_categories(call):
    chat_id = call.message.chat.id
    if call.data == "back_to_menu":
        bot.delete_message(chat_id, call.message.message_id)
        main_menu(chat_id, "মূল মেনু:")
        return

    if call.data == "doc_self":
        text = (
            "🇷🇺 *রাশিয়া Self fund ডকুমেন্টস তালিকা:*\n\n"
            "১. Academy marksheet certificate (SSC+HSC মাস্টার্স এর জন্য হলে bachelor মার্কশিট সার্টিফিকেট)\n"
            "২. পাসপোর্ট\n"
            "৩. একাডেমিক সকল সার্টিফিকেট এপোস্টিল\n"
            "৪. AFFIDAVIT\n"
            "৫. Bg: সাদা, ছবি ৩.৫×৪.৫ সেমি ল্যাব প্রিন্ট"
        )
    elif call.data == "doc_russia_sch":
        text = (
            "🇷🇺 *Russia Scholarship ডকুমেন্টস তালিকা:*\n\n"
            "১. Academy marksheet certificate (SSC+HSC মাস্টার্স এর জন্য হলে bachelor মার্কশিট সার্টিফিকেট)\n"
            "২. পাসপোর্ট\n"
            "৩. Phone Number\n"
            "৪. একাডেমিক সকল সার্টিফিকেট এপোস্টিল (যদি করা থাকে না থাকলে অনলাইন আবেদন করে নিন পরবর্তীতে লাগবে)\n"
            "৫. Bg: সাদা, ছবি পাসপোর্ট সাইজের।\n"
            "৬. স্বাক্ষর\n"
            "৭. achievement certificate (যদি থাকে)"
        )
    else:
        text = (
            "🏛️ *Embassy Document - Scholarship ডকুমেন্টস তালিকা:*\n\n"
            "১. Minister letter\n"
            "২. এপ্লিকেশন ফরম\n"
            "৩. ডিপ্লোমা সাটিফিকেট\n"
            "৪. মেডিকেল সাটিফিকেট\n"
            "৫. SSC+HSC সাটিফিকেট মার্ক শীট রজ্ঞিন + এপোসটিল\n"
            "৬. পাসপোর্ট ফটোকপি রঙিন + মেইন পাসপোর্ট\n"
            "৭. AFFIDAVIT\n"
            "৮. Qa: কপি\n"
            "৯. ভিসা পেমেন্ট সিলপ\n"
            "১০. ছবি ৩.৫×৪.৫ সেমি ল্যাব প্রিন্ট = ৩০-৪০ পিস"
        )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 পেছনে যান", callback_data="docs_guide"))
    bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)


# --- Support & Live Chat System ---
@bot.callback_query_handler(func=lambda call: call.data == "support_start")
def support_start(call):
    chat_id = call.message.chat.id
    bot.send_message(
        chat_id,
        "💬 সাপোর্ট সেকশনে স্বাগতম। আপনার রোল নম্বর উল্লেখ করে আপনার প্রশ্ন, ছবি বা ডকুমেন্ট এখানে পাঠিয়ে দিন। এডমিন খুব শীঘ্রই উত্তর দেবেন:",
    )
    # Forward subsequent messages to support topic until closed


@bot.message_handler(
    func=lambda message: message.chat.id not in ADMINS and message.text and not message.text.startswith("/")
)
def handle_user_messages_to_support(message):
    chat_id = message.chat.id
    text = message.text
    username = message.from_user.username or "No Username"

    forward_text = (
        f"💬 *Support Message*\n"
        f"👤 From: @{username} (ID: `{chat_id}`)\n"
        f"✉️ Message: {text}\n\n"
        f"*(উত্তর দিতে চাইলে রোল বা আইডি ট্যাগ করুন)*"
    )
    bot.send_message(
        BACKUP_GROUP_ID,
        forward_text,
        parse_mode="Markdown",
        message_thread_id=TOPIC_SUPPORT,
    )
    bot.send_message(chat_id, "✅ আপনার বার্তাটি সাপোর্টে পাঠানো হয়েছে।")


# Admin reply handling from the group topic
@bot.message_handler(
    func=lambda message: message.chat.id == BACKUP_GROUP_ID
    and message.message_thread_id == TOPIC_SUPPORT
    and message.reply_to_message
)
def handle_admin_reply(message):
    # Extract user ID from replied message or format
    reply_text = message.reply_to_message.text or ""
    import re
    match = re.search(r"ID: `(\d+)`", reply_text)
    if match:
        target_chat_id = int(match.group(1))
        bot.send_message(
            target_chat_id, f"👨‍💻 *Admin Support:* {message.text}", parse_mode="Markdown"
        )
        bot.reply_to(message, "✅ ইউজারের কাছে উত্তর পাঠানো হয়েছে।")


# --- In-Bot Admin Panel ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def admin_panel_menu(call):
    chat_id = call.message.chat.id
    if not is_admin(call.from_user.username):
        bot.answer_callback_query(call.id, "❌ আপনার এডমিন এক্সেস নেই!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ ইউজারের স্ট্যাটাস ও নোট আপডেট", callback_data="adm_up_status"),
        types.InlineKeyboardButton("📅 পরীক্ষার শিডিউল ও সাবজেক্ট সেট", callback_data="adm_up_exam"),
        types.InlineKeyboardButton("🔙 মূল মেনু", callback_data="back_to_menu")
    )
    bot.edit_message_text(
        "🛠️ *In-Bot Admin Panel*\n\nকন্ট্রোল করার জন্য অপশন সিলেক্ট করুন:",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "adm_up_status")
def adm_up_status_prompt(call):
    msg = bot.send_message(
        call.message.chat.id,
        "ইউজারের স্ট্যাটাস আপডেট করতে এই ফরমেটে লিখে পাঠান:\n`রোল, স্ট্যাটাস, নোট`\n\nউদাহরণ:\n`10001, In work, কাগজপত্র যাচাই চলছে`"
    )
    bot.register_next_step_handler(msg, save_admin_status_update)


def save_admin_status_update(message):
    try:
        parts = message.text.split(",", 2)
        roll = int(parts[0].strip())
        status = parts[1].strip()
        note = parts[2].strip()

        # Find user
        updated = False
        for u_id, u_data in users_db.items():
            if u_data["roll"] == roll:
                u_data["status"] = status
                u_data["status_note"] = note
                updated = True
                # Notify user directly
                bot.send_message(
                    u_id,
                    f"🔔 *আপনার স্ট্যাটাস আপডেট হয়েছে!*\n📌 Status: *{status}*\n📝 Note: {note}",
                    parse_mode="Markdown",
                )
                break

        if updated:
            bot.send_message(message.chat.id, "✅ স্ট্যাটাস সফলভাবে আপডেট করা হয়েছে।")
        else:
            bot.send_message(message.chat.id, "❌ এই রোল নম্বরের ইউজার পাওয়া যায়নি।")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ফরম্যাট ভুল হয়েছে। সঠিক ফরম্যাটে দিন।")


@bot.callback_query_handler(func=lambda call: call.data == "adm_up_exam")
def adm_up_exam_prompt(call):
    msg = bot.send_message(
        call.message.chat.id,
        "পরীক্ষার শিডিউল সেট করতে এই ফরমেটে লিখে পাঠান:\n`রোল, সাবজেক্ট, তারিখ, সময়`\n\nউদাহরণ:\n`10001, Russian Language, 15 August 2026, 10:00 AM`"
    )
    bot.register_next_step_handler(msg, save_admin_exam_update)


def save_admin_exam_update(message):
    try:
        parts = message.text.split(",", 3)
        roll = int(parts[0].strip())
        subject = parts[1].strip()
        date = parts[2].strip()
        time_str = parts[3].strip()

        updated = False
        for u_id, u_data in users_db.items():
            if u_data["roll"] == roll:
                u_data["exam_subject"] = subject
                u_data["exam_date"] = date
                u_data["exam_time"] = time_str
                updated = True
                bot.send_message(
                    u_id,
                    f"📚 *নতুন পরীক্ষার শিডিউল!*\nSubject: {subject}\nDate: {date}\nTime: {time_str}",
                    parse_mode="Markdown",
                )
                break

        if updated:
            bot.send_message(message.chat.id, "✅ পরীক্ষার শিডিউল সফলভাবে সেট করা হয়েছে।")
        else:
            bot.send_message(message.chat.id, "❌ রোল নম্বর পাওয়া যায়নি।")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ ফরম্যাট ভুল হয়েছে। আবার চেষ্টা করুন।")


# --- Active Check-in / Countdown Background Simulation ---
# (এখানে ব্যাকগ্রাউন্ডে থ্রেড বা ক্রন দিয়ে ১৫ মিনিট পরপর অ্যালার্ট ট্রিগার করার লজিক রাখা যায়)


# --- Run Bot ---
if __name__ == "__main__":
    print("Bot is running smoothly...")
    bot.infinity_polling()