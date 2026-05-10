import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import calendar
import re
import os
from flask import Flask

# ================= ⚙️ কনফিগারেশন =================
BOT_TOKEN = "8636640934:AAHrh_jJhZoe5O46mfvMDrc0UJ3IWE4CXGI"  
ADMIN_GROUP_ID = -1003984851079 

# 👇 এই ৩ জন ইউজারনেম অ্যাডমিন প্যানেল দেখতে ও কন্ট্রোল করতে পারবে
ALLOWED_ADMINS = ['bdhasan09', 'alexbd96', 'aminal041']

# টপিক আইডি (আপনার দেওয়া লিংক অনুযায়ী)
TOPIC_PAYMENT = 3       # ডিপোজিট/উত্তোলন
TOPIC_ATTENDANCE = 10   # Daily attendance
TOPIC_RECHARGE = 13     # recharge
TOPIC_HOURLY = 88       # Hourly report
TOPIC_LEAVE = 405       # sl-off-issue
# ===============================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
db_lock = threading.Lock()

# ================= 🛡️ হেল্পার ও সিকিউরিটি ফাংশন =================
def bd_time():
    """সবসময় সঠিক বাংলাদেশ সময় বের করার ফাংশন (Render সার্ভারের জন্য)"""
    return datetime.utcnow() + timedelta(hours=6)

def is_admin(user):
    """চেক করবে ইউজার অ্যাডমিন কি না"""
    if not user or not user.username: 
        return False
    return user.username.lower() in ALLOWED_ADMINS

def clean_text(text):
    """ইউজারের টেক্সট থেকে HTML ট্যাগ মুছে দেবে যাতে ফরম্যাট এরর না আসে"""
    if not text: return "N/A"
    return text.replace("<", "").replace(">", "").replace("&", "and")

def is_cmd(message):
    btns = ["/start", "/menu", "📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন", "⏱️ Daily Attendance", "📱 Recharges", "🩺 SL-OFF-issue", "👑 Admin Panel"]
    if message.text in btns:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.process_new_messages([message])
        return True
    return False

# ================= 🗄️ ডাটাবেস সেটআপ ও অটো-ফিক্স =================
def setup_db():
    with db_lock:
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # টেবিল তৈরি
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id INTEGER PRIMARY KEY, status TEXT, start_time TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS work_hours (user_id INTEGER, month_year TEXT, total_seconds INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS message_map (admin_msg_id INTEGER PRIMARY KEY, user_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS hourly_stats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, time TEXT, calls_h INTEGER, nsu_h INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports_log (user_id INTEGER, date TEXT, time TEXT, log TEXT)")
        
        # অটো কলাম আপডেট (পুরনো ডাটাবেস এরর ফিক্স)
        try: cursor.execute("ALTER TABLE attendance ADD COLUMN last_report_time TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE work_hours ADD COLUMN date TEXT")
        except: pass
            
        conn.commit()
        conn.close()

setup_db()

# ================= 🎛️ মেইন মেনু =================
def main_menu(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন")
    markup.add("⏱️ Daily Attendance", "📱 Recharges")
    markup.add("🩺 SL-OFF-issue")
    
    if is_admin(user):
        markup.add("👑 Admin Panel")
        
    return markup

def get_user_name(user_id):
    try:
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
            res = cursor.fetchone()
            conn.close()
            return res[0] if res else "Unknown User"
    except:
        return "Unknown User"

# ================= 🚀 স্টার্ট ও মেনু কমান্ড =================
@bot.message_handler(commands=['start'])
def start(message):
    name = get_user_name(message.chat.id)
    if name != "Unknown User":
        bot.send_message(message.chat.id, f"👇 <b>আপনার মেনু:</b>", reply_markup=main_menu(message.from_user))
    else:
        txt = "👋 <b>স্বাগতম সাপোর্ট প্যানেলে!</b>\nসিস্টেম ব্যবহারের জন্য আপনার <b>পুরো নাম</b> লিখে সেন্ড করুন।"
        msg = bot.send_message(message.chat.id, txt, reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, register)

def register(message):
    if is_cmd(message): return
    clean_name = clean_text(message.text)
    try:
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("REPLACE INTO users (user_id, name) VALUES (?, ?)", (message.chat.id, clean_name))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, f"🎊 <b>অভিনন্দন!</b>\nরেজিস্ট্রেশন সফল হয়েছে, {clean_name}।", reply_markup=main_menu(message.from_user))
    except Exception as e:
        bot.send_message(message.chat.id, "❌ রেজিস্ট্রেশনে সমস্যা হয়েছে। আবার /start দিন।")

@bot.message_handler(commands=['menu'])
def show_menu(message):
    bot.send_message(message.chat.id, "👇 <b>আপনার মেনু:</b>", reply_markup=main_menu(message.from_user))

# ================= 🚀 অ্যাডমিন রিপ্লাই =================
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_GROUP_ID and m.reply_to_message)
def handle_admin_reply(message):
    try:
        admin_reply_to_id = message.reply_to_message.message_id
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM message_map WHERE admin_msg_id = ?", (admin_reply_to_id,))
            res = cursor.fetchone()
            conn.close()
            
        if res:
            user_id = res[0]
            feedback = f"📩 <b>অ্যাডমিন রিপ্লাই:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.text)}"
            bot.send_message(user_id, feedback)
    except:
        pass

# ================= ১. 📊 আওয়ারলি রিপোর্ট =================
@bot.message_handler(func=lambda m: m.text == "📊 Hourly Report")
def hourly(message):
    name = get_user_name(message.chat.id)
    fmt = f"Caller Name: {name}\nTotal Call  (D): \nTotal NSU (D):\nTotal Call (H) :\nTotal NSU (H):"
    txt = f"📑 <b>নতুন আওয়ারলি রিপোর্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 নিচের বক্সে ক্লিক করে ফরম্যাটটি কপি করুন এবং <b>স্ক্রিনশটসহ</b> সাবমিট করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_hourly)

def save_hourly(message):
    if is_cmd(message): return
    if not message.photo:
        return bot.send_message(message.chat.id, "❌ <b>ভুল হয়েছে!</b> ছবি/স্ক্রিনশট ছাড়া রিপোর্ট সাবমিট হবেকারি হবে না।", reply_markup=main_menu(message.from_user))
    
    name = get_user_name(message.chat.id)
    caption_txt = clean_text(message.caption)
    
    # অটো ডাটা এক্সট্র্যাক্ট
    calls_h, nsu_h = 0, 0
    try:
        c_match = re.search(r"Total Call \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        n_match = re.search(r"Total NSU \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        if c_match: calls_h = int(c_match.group(1))
        if n_match: nsu_h = int(n_match.group(1))
    except: pass

    now = bd_time()
    time_now = now.strftime('%I:%M %p')
    date_now = now.strftime("%Y-%m-%d")
    
    report = f"📊 <b>HOURLY REPORT</b>\n👤 <b>User:</b> {name}\n⏰ <b>Time:</b> {time_now}\n━━━━━━━━━━━━━━━━━━\n📝 <b>Details:</b>\n{caption_txt}"
    
    try:
        sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_HOURLY)
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            cursor.execute("UPDATE attendance SET last_report_time = ? WHERE user_id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), message.chat.id))
            cursor.execute("INSERT INTO hourly_stats (user_id, date, time, calls_h, nsu_h) VALUES (?, ?, ?, ?, ?)", (message.chat.id, date_now, time_now, calls_h, nsu_h))
            cursor.execute("INSERT INTO reports_log (user_id, date, time, log) VALUES (?, ?, ?, ?)", (message.chat.id, date_now, time_now, caption_txt))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ আপনার আওয়ারলি রিপোর্ট সফলভাবে জমা হয়েছে।")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ সার্ভার এরর। আবার চেষ্টা করুন।")

# ================= ২. 💳 ডিপোজিট/উত্তোলন =================
@bot.message_handler(func=lambda m: m.text == "💳 ডিপোজিট/উত্তোলন")
def dep_with_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📥 ডিপোজিট", callback_data="req_dep"),
           types.InlineKeyboardButton("📤 উত্তোলন", callback_data="req_with"))
    bot.send_message(message.chat.id, "💳 <b>রিকুয়েস্ট ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['req_dep', 'req_with'])
def handle_dep_with(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    
    if call.data == "req_dep":
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nট্রানজেকশন আইডি: "
        txt = f"📥 <b>ডিপোজিট রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 বক্সে ক্লিক করে ফরম্যাটটি কপি করুন। <b>পেমেন্ট স্ক্রিনশটসহ</b> ক্যাপশনে পূরণ করে সাবমিট করুন:\n\n<code>{fmt}</code>"
        msg = bot.send_message(call.message.chat.id, txt)
        bot.register_next_step_handler(msg, lambda m: save_transaction(m, "DEPOSIT"))
    else:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nলেনদেন আইডি: \nঅ্যামাউন্ট: "
        txt = f"📤 <b>উত্তোলন রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 বক্সে ক্লিক করে ফরম্যাটটি কপি করুন এবং পূরণ করে সাবমিট করুন:\n\n<code>{fmt}</code>"
        msg = bot.send_message(call.message.chat.id, txt)
        bot.register_next_step_handler(msg, lambda m: save_transaction(m, "WITHDRAWAL"))

def save_transaction(message, req_type):
    if is_cmd(message): return
    if req_type == "DEPOSIT" and not message.photo:
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া ডিপোজিট রিকোয়েস্ট নেওয়া হবে না।", reply_markup=main_menu(message.from_user))
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.caption else message.text)
    report = f"💰 <b>{req_type} REQUEST</b>\n👤 <b>User:</b> {name}\n📝 <b>Details:</b>\n{cap}"
    
    try:
        if message.photo:
            sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_PAYMENT)
        else:
            sent = bot.send_message(ADMIN_GROUP_ID, report, message_thread_id=TOPIC_PAYMENT)
            
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ আপনার রিকুয়েষ্ট এডমিনের কাছে পাঠানো হয়েছে। আপডেটের জন্য অপেক্ষা করুন।")
    except: 
        bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

# ================= ৩. ⏱️ Daily Attendance (Pro Logic) =================
@bot.message_handler(func=lambda m: m.text == "⏱️ Daily Attendance")
def attend_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🟢 ডিউটি শুরু", callback_data="sw"),
           types.InlineKeyboardButton("⏸️ বিরতি", callback_data="bw"))
    kb.add(types.InlineKeyboardButton("🔴 ডিউটি শেষ", callback_data="pw"))
    bot.send_message(message.chat.id, "⏱️ <b>এটেনডেন্স প্যানেল</b>\nআপনার বর্তমান ডিউটি স্ট্যাটাস আপডেট করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['sw', 'bw', 'pw'])
def attend_call(call):
    try: bot.answer_callback_query(call.id, "প্রসেস হচ্ছে...")
    except: pass

    uid = call.message.chat.id
    name = get_user_name(uid)
    now = bd_time()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    disp_time = now.strftime('%I:%M %p')
    display_date = now.strftime("%d %B %Y")

    try:
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            
            cursor.execute("INSERT OR IGNORE INTO attendance (user_id, status) VALUES (?, 'stopped')", (uid,))
            cursor.execute("SELECT status, start_time FROM attendance WHERE user_id=?", (uid,))
            row = cursor.fetchone()
            current_status = row[0] if row else 'stopped'
            start_str = row[1] if row else None

            # 🟢 ডিউটি শুরু
            if call.data == 'sw':
                if current_status == 'working':
                    bot.send_message(uid, "⚠️ আপনি ইতিমধ্যেই কাজে অ্যাক্টিভ আছেন!")
                else:
                    msg_text = "🟢 <b>Duty Resumed (বিরতি থেকে ফিরলো)</b>" if current_status == 'break' else "🟢 <b>Duty Started</b>"
                    cursor.execute("UPDATE attendance SET status='working', start_time=?, last_report_time=? WHERE user_id=?", (time_str, time_str, uid))
                    try: bot.send_message(ADMIN_GROUP_ID, f"{msg_text}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}\n📅 <b>Date:</b> {display_date}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>আপনার ডিউটি শুরু হয়েছে!</b> (কাজের মিটার চালু)", uid, call.message.message_id, parse_mode="HTML")

            # ⏸️ বিরতি
            elif call.data == 'bw':
                if current_status == 'break':
                    bot.send_message(uid, "⚠️ আপনি ইতিমধ্যেই বিরতিতে আছেন!")
                elif current_status == 'stopped':
                    bot.send_message(uid, "⚠️ আপনি এখনো কাজে ঢোকেননি!")
                else:
                    try: st = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    except: st = now
                    sec = max(int((now - st).total_seconds()), 0)

                    cursor.execute("SELECT 1 FROM work_hours WHERE user_id=? AND date=?", (uid, date_str))
                    if not cursor.fetchone(): cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (?, ?, 0)", (uid, date_str))
                    cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + ? WHERE user_id = ? AND date = ?", (sec, uid, date_str))
                    cursor.execute("UPDATE attendance SET status='break' WHERE user_id=?", (uid,))
                    
                    try: bot.send_message(ADMIN_GROUP_ID, f"⏸️ <b>Break Taken (বিরতি শুরু)</b>\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>আপনার বিরতি শুরু হয়েছে!</b> (কাজের মিটার পজ)", uid, call.message.message_id, parse_mode="HTML")

            # 🔴 ডিউটি শেষ
            elif call.data == 'pw':
                if current_status == 'stopped':
                    bot.send_message(uid, "⚠️ আপনার ডিউটি আগেই শেষ হয়েছে!")
                else:
                    if current_status == 'working':
                        try: st = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                        except: st = now
                        sec = max(int((now - st).total_seconds()), 0)
                        cursor.execute("SELECT 1 FROM work_hours WHERE user_id=? AND date=?", (uid, date_str))
                        if not cursor.fetchone(): cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (?, ?, 0)", (uid, date_str))
                        cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + ? WHERE user_id = ? AND date = ?", (sec, uid, date_str))

                    cursor.execute("UPDATE attendance SET status='stopped' WHERE user_id=?", (uid,))
                    try: bot.send_message(ADMIN_GROUP_ID, f"🔴 <b>Duty Ended (ডিউটি শেষ)</b>\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}\n📅 <b>Date:</b> {display_date}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>আপনার ডিউটি শেষ হয়েছে।</b> (সারাদিনের কাজ সেভড)", uid, call.message.message_id, parse_mode="HTML")

            conn.commit()
            conn.close()
    except Exception as e:
        bot.send_message(uid, f"❌ এটেনডেন্স আপডেট করতে সমস্যা হয়েছে।")

# ================= ৪. 📱 Recharges =================
@bot.message_handler(func=lambda m: m.text == "📱 Recharges")
def recharge_app(message):
    fmt = "তারিখ: \nমাস: \nবছর: \nঅ্যামাউন্ট: "
    txt = f"📱 <b>রিচার্জ রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 ফরম্যাটটি কপি করুন। <b>অবশ্যই স্ক্রিনশট সিলেক্ট করে</b> ক্যাপশনে এটি পূরণ করে সাবমিট করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_recharge)

def save_recharge(message):
    if is_cmd(message): return
    if not message.photo:
        return bot.send_message(message.chat.id, "❌ <b>ভুল!</b> স্ক্রিনশট ছাড়া রিচার্জ রিকোয়েস্ট গ্রহন হবে না।", reply_markup=main_menu(message.from_user))
    
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption)
    report = f"📱 <b>RECHARGE REQUEST</b>\n👤 <b>User:</b> {name}\n📝 <b>Details:</b>\n{cap}"
    try:
        sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_RECHARGE)
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ আপনার রিকুয়েষ্ট এডমিন কাছে পাঠানো হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

# ================= ৫. 🩺 SL-OFF-issue =================
@bot.message_handler(func=lambda m: m.text == "🩺 SL-OFF-issue")
def leave_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🤒 অসুস্থ ছুটি", callback_data="lv_sick"),
           types.InlineKeyboardButton("🚨 ইমারজেন্সি ছুটি", callback_data="lv_emg"),
           types.InlineKeyboardButton("⚠️ সমস্যা", callback_data="lv_issue"))
    bot.send_message(message.chat.id, "🩺 <b>ছুটি বা সমস্যার ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('lv_'))
def handle_leave(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    title = "অসুস্থ ছুটি" if call.data == "lv_sick" else ("ইমারজেন্সি ছুটি" if call.data == "lv_emg" else "সমস্যা")
    fmt = "তারিখ: \nবিস্তারিত: \nকত দিন: "
    txt = f"📝 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━\nনিচের ফরম্যাটটি কপি করে বিস্তারিত লিখে সেন্ড করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(call.message.chat.id, txt)
    bot.register_next_step_handler(msg, lambda m: save_leave_data(m, title))

def save_leave_data(message, title):
    if is_cmd(message): return
    name = get_user_name(message.chat.id)
    cap = clean_text(message.text)
    report = f"🩺 <b>{title.upper()}</b>\n👤 <b>User:</b> {name}\n📝 <b>Details:</b>\n{cap}"
    try:
        sent = bot.send_message(ADMIN_GROUP_ID, report, message_thread_id=TOPIC_LEAVE)
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ আপনার রিপোর্ট এডমিন গ্রুপে পাঠানো হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

# ================= 👑 ৬,৭,৮: ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_menu(message):
    if not is_admin(message.from_user):
        bot.send_message(message.chat.id, "⛔ <b>অ্যাক্সেস ডিনাইড!</b>\nএই প্যানেলটি শুধুমাত্র অ্যাডমিনের জন্য।")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📋 ইউজার রিপোর্ট চেক করুন", callback_data="admin_check"),
        types.InlineKeyboardButton("🏆 Best Performer ঘোষণা", callback_data="admin_best"),
        types.InlineKeyboardButton("👤 ইউজার ম্যানেজমেন্ট", callback_data="admin_manage"),
        types.InlineKeyboardButton("📢 প্রমোশন মেসেজ পাঠান", callback_data="admin_promo")
    )
    bot.send_message(message.chat.id, "👑 <b>অ্যাডমিন কন্ট্রোল প্যানেল:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('admin_'))
def handle_admin_actions(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    if not is_admin(call.from_user): return
    
    if call.data == "admin_check":
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, name FROM users")
            users = cursor.fetchall()
            conn.close()
        if not users:
            bot.send_message(call.message.chat.id, "⚠️ কোনো ইউজার নেই।")
            return
        kb = types.InlineKeyboardMarkup()
        for u in users: kb.add(types.InlineKeyboardButton(u[1], callback_data=f"rpt_{u[0]}"))
        bot.send_message(call.message.chat.id, "📊 <b>কার রিপোর্ট দেখতে চান?</b>", reply_markup=kb)
        
    elif call.data == "admin_best":
        # প্রথমে অ্যাডমিনকে আজকের সেরা কে, সেটা জানিয়ে সাহায্য করা
        today = bd_time().strftime("%Y-%m-%d")
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT u.name, SUM(h.nsu_h), SUM(h.calls_h) FROM hourly_stats h JOIN users u ON h.user_id = u.user_id WHERE h.date=? GROUP BY h.user_id ORDER BY SUM(h.nsu_h) DESC, SUM(h.calls_h) DESC LIMIT 1", (today,))
            best = cursor.fetchone()
            conn.close()
            
        helper_txt = ""
        if best and best[0]:
            helper_txt = f"(আজকের শীর্ষে আছে: <b>{best[0]}</b> | NSU: {best[1]})\n\n"
            
        txt = f"🏆 <b>Best Performer ঘোষণা</b>\n\n{helper_txt}যাকে সেরা ঘোষণা করবেন, তার জন্য একটি সুন্দর টেক্সট লিখুন এবং চাইলে একটি <b>ছবিসহ (Caption)</b> সেন্ড করুন। এটি সবার ইনবক্সে যাবে।"
        msg = bot.send_message(call.message.chat.id, txt)
        bot.register_next_step_handler(msg, send_best_performer)
            
    elif call.data == "admin_promo":
        msg = bot.send_message(call.message.chat.id, "📢 <b>প্রমোশন মেসেজ:</b>\nযে নোটিশটি সবার কাছে পাঠাতে চান, তা লিখে সেন্ড করুন (ছবিও দিতে পারেন):")
        bot.register_next_step_handler(msg, lambda m: broadcast_msg(m, is_promo=True))
        
    elif call.data == "admin_manage":
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, name FROM users")
            users = cursor.fetchall()
            conn.close()
        kb = types.InlineKeyboardMarkup()
        for u in users: kb.add(types.InlineKeyboardButton(f"❌ Remove: {u[1]}", callback_data=f"del_{u[0]}"))
        bot.edit_message_text("👤 <b>কাকে রিমুভ করতে চান?</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

def send_best_performer(message):
    if is_cmd(message): return
    caption = clean_text(message.caption if message.photo else message.text)
    txt = f"🌟 <b>সেরা পারফর্মার!</b> 🌟\n━━━━━━━━━━━━━━━━━━\n\n{caption}\n\n━━━━━━━━━━━━━━━━━━\n🚀 <i>অভিনন্দন! আপনার ডেডিকেশন আমাদের মুগ্ধ করেছে।</i>"
    broadcast_to_all(message, txt, message.photo)

def broadcast_msg(message, is_promo=False):
    if is_cmd(message): return
    caption = clean_text(message.caption if message.photo else message.text)
    prefix = "📢 <b>অ্যাডমিন নোটিশ:</b>\n━━━━━━━━━━━━━━━━━━\n" if is_promo else ""
    txt = f"{prefix}{caption}\n━━━━━━━━━━━━━━━━━━"
    broadcast_to_all(message, txt, message.photo)

def broadcast_to_all(message, text, photo):
    with db_lock:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
    count = 0
    for u in users:
        try:
            if photo: bot.send_photo(u[0], photo[-1].file_id, caption=text)
            else: bot.send_message(u[0], text)
            count += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ মেসেজটি সফলভাবে {count} জনের কাছে পাঠানো হয়েছে।")

@bot.callback_query_handler(func=lambda c: c.data.startswith('del_'))
def delete_user(call):
    if not is_admin(call.from_user): return
    uid = call.data.split('_')[1]
    with db_lock:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
        cursor.execute("DELETE FROM attendance WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
    bot.edit_message_text("✅ ইউজারকে সফলভাবে ডাটাবেস থেকে মুছে ফেলা হয়েছে।", call.message.chat.id, call.message.message_id)

# ================= 🔍 রিপোর্ট ফিল্টার =================
@bot.callback_query_handler(func=lambda c: c.data.startswith('rpt_'))
def select_report_range(call):
    if not is_admin(call.from_user): return
    uid = call.data.split('_')[1]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("২৪ ঘন্টা", callback_data=f"dr_{uid}_1"),
           types.InlineKeyboardButton("৭ দিন", callback_data=f"dr_{uid}_7"),
           types.InlineKeyboardButton("১৫ দিন", callback_data=f"dr_{uid}_15"),
           types.InlineKeyboardButton("৩০ দিন", callback_data=f"dr_{uid}_30"))
    bot.edit_message_text("⏳ <b>কত দিনের রিপোর্ট দেখতে চান?</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('dr_'))
def show_final_report(call):
    if not is_admin(call.from_user): return
    parts = call.data.split('_')
    uid, days = int(parts[1]), int(parts[2])
    target_date = (bd_time() - timedelta(days=days-1)).strftime("%Y-%m-%d")
    
    with db_lock:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id=?", (uid,))
        res = cursor.fetchone()
        name = res[0] if res else "Unknown"
        
        cursor.execute("SELECT SUM(total_seconds) FROM work_hours WHERE user_id=? AND date >= ?", (uid, target_date))
        total_sec = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(calls_h), SUM(nsu_h), COUNT(*) FROM hourly_stats WHERE user_id=? AND date >= ?", (uid, target_date))
        stat = cursor.fetchone()
        t_calls, t_nsu, t_reports = stat[0] or 0, stat[1] or 0, stat[2] or 0
        
        cursor.execute("SELECT date, time, log FROM reports_log WHERE user_id=? AND date >= ?", (uid, target_date))
        logs = cursor.fetchall()
        conn.close()
        
    h, m = total_sec // 3600, (total_sec % 3600) // 60
    txt = f"📊 <b>Full Report: {name}</b>\n📅 <b>Range:</b> Last {days} Days\n━━━━━━━━━━━━━━━━━━\n"
    txt += f"⏳ <b>মোট কাজের সময়:</b> {h} ঘণ্টা {m} মিনিট\n📑 <b>Hourly সাবমিট:</b> {t_reports} বার\n"
    txt += f"📞 <b>Total Calls:</b> {t_calls}\n📉 <b>Total NSU:</b> {t_nsu}\n━━━━━━━━━━━━━━━━━━\n\n"
    
    if logs:
        txt += "📝 <b>সাবমিট করা রিপোর্টসমূহ:</b>\n"
        for l in logs[-5:]:
            txt += f"[{l[0]} | {l[1]}] {l[2][:50]}...\n"
            
    try: bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except: pass

# ================= 🤖 অটোমেশন ও অ্যালার্ট =================
def automation():
    best_performer_alert_sent = False
    while True:
        try:
            now = bd_time()
            
            # ১. রাত ১০:১৫ তে শুধু অ্যাডমিনদের অ্যালার্ট (বাংলাদেশ টাইমে)
            if now.hour == 22 and now.minute == 15 and not best_performer_alert_sent:
                alert_text = f"🔔 <b>অ্যাডমিন অ্যালার্ট:</b>\nরাত ১০:১৫ বেজেছে! এখন আজকের <b>'Best Performer'</b> ঘোষণা করার সময়। দয়া করে অ্যাডমিন প্যানেল থেকে আজকের সেরা পারফর্মার নির্বাচন করে সবার কাছে পাঠিয়ে দিন।"
                try: bot.send_message(ADMIN_GROUP_ID, alert_text)
                except: pass
                best_performer_alert_sent = True

            if now.hour == 0: 
                best_performer_alert_sent = False 

            # ২. আওয়ারলি রিপোর্ট রিমাইন্ডার (শুধুমাত্র ডিউটিতে থাকা নন-অ্যাডমিনদের)
            if now.minute % 15 == 0:
                with db_lock:
                    conn = sqlite3.connect('bot_database.db')
                    cursor = conn.cursor()
                    # শুধুমাত্র যারা "working" (কাজে অ্যাক্টিভ) আছে তাদের চেক করবে
                    cursor.execute("SELECT user_id, last_report_time FROM attendance WHERE status='working'")
                    for u, lr in cursor.fetchall():
                        is_u_admin = False
                        try:
                            member = bot.get_chat_member(ADMIN_GROUP_ID, u)
                            if member.status in ['administrator', 'creator']: is_u_admin = True
                        except: pass
                        
                        if not is_u_admin:
                            if lr and (now - datetime.strptime(lr, "%Y-%m-%d %H:%M:%S")).total_seconds() >= 3600:
                                try: bot.send_message(u, "📢 <b>Hourly report টাইম হয়েছে!</b> দয়া করে আপনার রিপোর্ট সাবমিট করুন।")
                                except: pass
                                cursor.execute("UPDATE attendance SET last_report_time = ? WHERE user_id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), u))
                    conn.commit()
                    conn.close()
            time.sleep(60)
        except Exception as e: 
            print(f"Automation Error: {e}")
            time.sleep(60)

threading.Thread(target=automation, daemon=True).start()

# ================= 🚀 রান বট ও রেন্ডার সার্ভার =================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is Online & Running 24/7 on Render!"

def run_bot():
    print("🚀 Bot is Online! Ultimate Pro Version with Solid Error Handling Activated.")
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
    except Exception as e: 
        print("Critical Error:", e)

# বটকে ব্যাকগ্রাউন্ডে চালু করা
threading.Thread(target=run_bot, daemon=True).start()

# মেইন থ্রেডে ওয়েব সার্ভার চালু করা (যাতে Render কখনো বন্ধ না করে)
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
