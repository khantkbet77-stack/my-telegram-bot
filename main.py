import telebot
from telebot import types
import psycopg2
from datetime import datetime, timedelta
import threading
import time
import re
import os
from flask import Flask

# =======================================================
# ⚙️ কনফিগারেশন এবং সেটআপ (Configuration)
# =======================================================
BOT_TOKEN = "8636640934:AAHrh_jJhZoe5O46mfvMDrc0UJ3IWE4CXGI"  
ADMIN_GROUP_ID = -1003984851079 

# যারা অ্যাডমিন প্যানেল কন্ট্রোল করবে
ALLOWED_ADMINS = ['bdhasan09', 'alexbd96', 'aminal041']
ADMIN_MENTION = "@AlexBD96"

# টপিক আইডি সমূহ (আপনার দেওয়া)
TOPIC_PAYMENT = 3       
TOPIC_ATTENDANCE = 10   
TOPIC_RECHARGE = 13     
TOPIC_HOURLY = 88       
TOPIC_LEAVE = 405       

# আপনার ক্লাউড ডাটাবেস ইউআরএল (Neon DB)
DB_URL = "postgresql://neondb_owner:npg_Efms7N5AzDZx@ep-fragrant-shape-aou3wk2j.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

# বট ইনিশিয়ালাইজ
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# =======================================================
# 🛡️ প্রয়োজনীয় ফাংশন সমূহ (Helper Functions)
# =======================================================
def get_conn():
    """ডাটাবেসের সাথে কানেকশন তৈরি করার ফাংশন"""
    return psycopg2.connect(DB_URL)

def bd_time():
    """সবসময় সঠিক বাংলাদেশ সময় (UTC+6) বের করার ফাংশন"""
    return datetime.utcnow() + timedelta(hours=6)

def is_admin(user):
    """চেক করবে ইউজার অ্যাডমিন কি না"""
    if not user or not user.username: 
        return False
    return user.username.lower() in ALLOWED_ADMINS

def clean_text(text):
    """টেক্সট থেকে এরর সৃষ্টিকারী ট্যাগ মুছে ফেলার ফাংশন"""
    if not text: 
        return "N/A"
    return text.replace("<", "").replace(">", "").replace("&", "and")

def is_cmd(message):
    """চেক করবে মেসেজটি কোনো বাটন বা কমান্ড কি না"""
    btns = ["/start", "/menu", "📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন", "⏱️ Daily Attendance", "📱 Recharges", "🩺 SL-OFF-issue", "👑 Admin Panel"]
    if message.text in btns:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.process_new_messages([message])
        return True
    return False

# =======================================================
# 🗄️ ক্লাউড ডাটাবেস টেবিল তৈরি (Database Setup)
# =======================================================
def setup_db():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # ইউজারদের ডাটাবেস
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT)")
        
        # এটেনডেন্স ডাটাবেস
        cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id BIGINT PRIMARY KEY, status TEXT, start_time TEXT, last_report_time TEXT, last_break_time TEXT)")
        
        # কাজের হিসাব
        cursor.execute("CREATE TABLE IF NOT EXISTS work_hours (user_id BIGINT, date TEXT, total_seconds INTEGER DEFAULT 0, UNIQUE(user_id, date))")
        
        # অ্যাডমিন রিপ্লাইয়ের জন্য মেসেজ ম্যাপ
        cursor.execute("CREATE TABLE IF NOT EXISTS message_map (admin_msg_id BIGINT PRIMARY KEY, user_id BIGINT)")
        
        # আওয়ারলি স্ট্যাটাস
        cursor.execute("CREATE TABLE IF NOT EXISTS hourly_stats (id SERIAL PRIMARY KEY, user_id BIGINT, date TEXT, time TEXT, calls_h INTEGER, nsu_h INTEGER)")
        
        # সব রিপোর্টের লগ
        cursor.execute("CREATE TABLE IF NOT EXISTS reports_log (user_id BIGINT, date TEXT, time TEXT, log TEXT)")
        
        conn.commit()
        conn.close()
        print("✅ Database connection and setup successful!")
    except Exception as e:
        print("❌ DB Setup Error:", e)

setup_db()

# =======================================================
# 🎛️ মেইন মেনু কীবোর্ড (Main Menu)
# =======================================================
def main_menu(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন")
    markup.add("⏱️ Daily Attendance", "📱 Recharges")
    markup.add("🩺 SL-OFF-issue")
    
    # যদি ইউজার অ্যাডমিন হয় তবে অ্যাডমিন প্যানেল দেখাবে
    if is_admin(user): 
        markup.add("👑 Admin Panel")
        
    return markup

def get_user_name(user_id):
    """ডাটাবেস থেকে ইউজারের নাম বের করার ফাংশন"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id = %s", (user_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            return res[0]
        else:
            return "Unknown User"
    except: 
        return "Unknown User"

# =======================================================
# 🚀 স্টার্ট ও রেজিস্ট্রেশন (Start & Registration)
# =======================================================
@bot.message_handler(commands=['start', 'menu'])
def start(message):
    name = get_user_name(message.chat.id)
    
    if name != "Unknown User":
        # যদি আগে থেকে রেজিস্টার করা থাকে
        bot.send_message(message.chat.id, f"👇 <b>আপনার মেনু:</b>", reply_markup=main_menu(message.from_user))
    else:
        # যদি নতুন ইউজার হয়
        msg = bot.send_message(message.chat.id, "👋 <b>স্বাগতম সাপোর্ট প্যানেলে!</b>\nসিস্টেম ব্যবহারের জন্য আপনার <b>পুরো নাম</b> লিখে সেন্ড করুন।")
        bot.register_next_step_handler(msg, register)

def register(message):
    if is_cmd(message): return
    clean_name = clean_text(message.text)
    
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name", (message.chat.id, clean_name))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, f"🎊 রেজিস্ট্রেশন সফল! স্বাগতম <b>{clean_name}</b>।", reply_markup=main_menu(message.from_user))
    except Exception as e:
        bot.send_message(message.chat.id, "❌ রেজিস্ট্রেশনে সমস্যা হয়েছে। আবার /start দিন।")

# =======================================================
# 🚀 অ্যাডমিন রিপ্লাই (Admin Reply System)
# =======================================================
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_GROUP_ID and m.reply_to_message)
def handle_admin_reply(message):
    try:
        admin_reply_to_id = message.reply_to_message.message_id
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM message_map WHERE admin_msg_id = %s", (admin_reply_to_id,))
        res = cursor.fetchone()
        conn.close()
        
        if res:
            user_id = res[0]
            feedback = f"📩 <b>অ্যাডমিন রিপ্লাই:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.text)}"
            bot.send_message(user_id, feedback)
    except: 
        pass

# =======================================================
# ১. 📊 আওয়ারলি রিপোর্ট (Hourly Report)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "📊 Hourly Report")
def hourly(message):
    name = get_user_name(message.chat.id)
    
    # আপনার দেওয়া হুবহু ফরম্যাট
    fmt = f"Caller Name: {name}\nTotal Call  (D): \nTotal NSU (D):\nTotal Call (H) :\nTotal NSU (H):"
    txt = f"📑 <b>নতুন আওয়ারলি রিপোর্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 নিচের বক্সে ক্লিক করে ফরম্যাটটি কপি করুন এবং <b>স্ক্রিনশটসহ</b> সাবমিট করুন:\n\n<code>{fmt}</code>"
    
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_hourly)

def save_hourly(message):
    if is_cmd(message): return
    
    if not message.photo:
        return bot.send_message(message.chat.id, "❌ <b>ভুল হয়েছে!</b> ছবি/স্ক্রিনশট ছাড়া রিপোর্ট সাবমিট হবে না।")
    
    name = get_user_name(message.chat.id)
    caption_txt = clean_text(message.caption)
    
    # অটো ডাটা এক্সট্র্যাক্ট করা (ক্যালকুলেশনের জন্য)
    calls_h = 0
    nsu_h = 0
    try:
        c_match = re.search(r"Total Call \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        n_match = re.search(r"Total NSU \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        if c_match: calls_h = int(c_match.group(1))
        if n_match: nsu_h = int(n_match.group(1))
    except: 
        pass

    now = bd_time()
    time_now = now.strftime('%I:%M %p')
    date_now = now.strftime("%Y-%m-%d")
    
    report = f"📊 <b>HOURLY REPORT</b>\n👤 <b>User:</b> {name}\n⏰ <b>Time:</b> {time_now}\n━━━━━━━━━━━━━━━━━━\n📝 <b>Details:</b>\n{caption_txt}"
    
    try:
        sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_HOURLY)
        
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (%s, %s) ON CONFLICT (admin_msg_id) DO NOTHING", (sent.message_id, message.chat.id))
        cursor.execute("UPDATE attendance SET last_report_time = %s WHERE user_id = %s", (now.strftime("%Y-%m-%d %H:%M:%S"), message.chat.id))
        cursor.execute("INSERT INTO hourly_stats (user_id, date, time, calls_h, nsu_h) VALUES (%s, %s, %s, %s, %s)", (message.chat.id, date_now, time_now, calls_h, nsu_h))
        cursor.execute("INSERT INTO reports_log (user_id, date, time, log) VALUES (%s, %s, %s, %s)", (message.chat.id, date_now, time_now, caption_txt))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ আপনার আওয়ারলি রিপোর্ট সফলভাবে জমা হয়েছে।")
    except: 
        bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

# =======================================================
# ২. 💳 ডিপোজিট/উত্তোলন (Deposit & Withdraw)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "💳 ডিপোজিট/উত্তোলন")
def dep_with_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📥 ডিপোজিট", callback_data="req_dep"),
        types.InlineKeyboardButton("📤 উত্তোলন", callback_data="req_with")
    )
    bot.send_message(message.chat.id, "💳 <b>রিকুয়েস্ট ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['req_dep', 'req_with'])
def handle_dep_with(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    
    is_dep = (call.data == "req_dep")
    
    if is_dep:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nট্রানজেকশন আইডি: \nনোট: "
    else:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nলেনদেন আইডি: \nঅ্যামাউন্ট: \nনোট: "
        
    txt = f"💳 <b>{'ডিপোজিট' if is_dep else 'উত্তোলন'} রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 ফরম্যাটটি কপি করে পূরণ করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(call.message.chat.id, txt)
    
    bot.register_next_step_handler(msg, lambda m: save_transaction(m, "DEPOSIT" if is_dep else "WITHDRAWAL"))

def save_transaction(message, req_type):
    if is_cmd(message): return
    
    if req_type == "DEPOSIT" and not message.photo:
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া ডিপোজিট রিকোয়েস্ট হবে না।")
    
    name = get_user_name(message.chat.id)
    caption = clean_text(message.caption if message.photo else message.text)
    
    # মেনশন সহ মেসেজ 
    report = f"💰 <b>{req_type} REQUEST</b>\n👤 <b>User:</b> {name}\n📢 <b>Admin:</b> {ADMIN_MENTION}\n📝 <b>Details:</b>\n{caption}"
    
    try:
        if message.photo:
            sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_PAYMENT)
        else:
            sent = bot.send_message(ADMIN_GROUP_ID, report, message_thread_id=TOPIC_PAYMENT)
        
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (%s, %s) ON CONFLICT (admin_msg_id) DO NOTHING", (sent.message_id, message.chat.id))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ অ্যাডমিনকে রিকোয়েস্ট পাঠানো হয়েছে।")
    except: 
        bot.send_message(message.chat.id, "❌ এরর হয়েছে।")

# =======================================================
# ৩. ⏱️ Daily Attendance (Attendance Panel)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "⏱️ Daily Attendance")
def attend_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🟢 ডিউটি শুরু", callback_data="sw"),
        types.InlineKeyboardButton("⏸️ বিরতি", callback_data="bw")
    )
    kb.add(types.InlineKeyboardButton("🔴 ডিউটি শেষ", callback_data="pw"))
    
    bot.send_message(message.chat.id, "⏱️ <b>এটেনডেন্স প্যানেল</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['sw', 'bw', 'pw'])
def attend_call(call):
    try: bot.answer_callback_query(call.id, "প্রসেস হচ্ছে...")
    except: pass
    
    uid = call.message.chat.id
    name = get_user_name(uid)
    now = bd_time()
    
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    disp_time = now.strftime('%I:%M %p')
    date_str = now.strftime("%d %B %Y")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (user_id, status) VALUES (%s, 'stopped') ON CONFLICT (user_id) DO NOTHING", (uid,))
    cursor.execute("SELECT status, start_time FROM attendance WHERE user_id=%s", (uid,))
    row = cursor.fetchone()
    current_status = row[0]

    if call.data == 'sw':
        if current_status == 'break':
            msg_text = "🟢 <b>Duty Resumed (বিরতি থেকে ফিরলো)</b>"
        else:
            msg_text = "🟢 <b>Duty Started</b>"
            
        cursor.execute("UPDATE attendance SET status='working', start_time=%s, last_report_time=%s WHERE user_id=%s", (time_str, time_str, uid))
        
        bot.send_message(ADMIN_GROUP_ID, f"{msg_text}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}\n📅 <b>Date:</b> {date_str}", message_thread_id=TOPIC_ATTENDANCE)
        bot.edit_message_text("✅ <b>আপনার ডিউটি শুরু হয়েছে!</b> (কাজের মিটার চালু)", uid, call.message.message_id)

    elif call.data == 'bw':
        cursor.execute("UPDATE attendance SET status='break', last_break_time=%s WHERE user_id=%s", (time_str, uid))
        
        bot.send_message(ADMIN_GROUP_ID, f"⏸️ <b>Break Taken</b>\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
        bot.edit_message_text("✅ <b>আপনার বিরতি শুরু হয়েছে!</b> (কাজের মিটার পজ)", uid, call.message.message_id)

    elif call.data == 'pw':
        cursor.execute("UPDATE attendance SET status='stopped' WHERE user_id=%s", (uid,))
        
        bot.send_message(ADMIN_GROUP_ID, f"🔴 <b>Duty Ended</b>\n👤 <b>Name:</b> {name}\n⏰ <b>Time:</b> {disp_time}\n📅 <b>Date:</b> {date_str}", message_thread_id=TOPIC_ATTENDANCE)
        bot.edit_message_text("✅ <b>আপনার ডিউটি শেষ হয়েছে।</b> (কাজ সেভড)", uid, call.message.message_id)

    conn.commit()
    conn.close()

# =======================================================
# ৪. 📱 Recharges (Recharge Request)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "📱 Recharges")
def recharge_app(message):
    fmt = "তারিখ: \nপেমেন্ট সিস্টেম: \nএমাউন্টও: "
    txt = f"📱 <b>রিচার্জ রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 ফরম্যাটটি কপি করে পূরণ করুন। <b>স্ক্রিনশটসহ</b> সাবমিট করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_recharge)

def save_recharge(message):
    if is_cmd(message): return
    
    if not message.photo:
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া রিচার্জ রিকোয়েস্ট হবে না।")
        
    name = get_user_name(message.chat.id)
    caption = clean_text(message.caption)
    
    report = f"📱 <b>RECHARGE</b>\n👤 {name}\n📝 {caption}"
    
    try:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_RECHARGE)
        bot.send_message(message.chat.id, "✅ রিচার্জ রিকোয়েস্ট পাঠানো হয়েছে।")
    except:
        bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

# =======================================================
# ৫. 🩺 SL-OFF-issue (Leave Management)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "🩺 SL-OFF-issue")
def leave_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🤒 অসুস্থ ছুটি", callback_data="lv_sick"),
        types.InlineKeyboardButton("⏳ অতিরিক্ত বিরতি সময়", callback_data="lv_extra"),
        types.InlineKeyboardButton("🆘 ইমারজেন্সি কাজ", callback_data="lv_emg")
    )
    bot.send_message(message.chat.id, "🩺 <b>ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('lv_'))
def handle_leave(call):
    if call.data == "lv_sick":
        fmt = "তারিখ: \nবিস্তারিত: \nদিন: "
        mode = "SICK LEAVE"
    elif call.data == "lv_extra":
        fmt = "বিরতি শুরু সময়: \nবিরতি শেষ সময়: \nমোট সময়: "
        mode = "EXTRA BREAK"
    else:
        fmt = "তারিখ: \nকারণ: \nডকুমেন্টস: "
        mode = "EMERGENCY WORK"
    
    txt = f"📝 <b>{mode}</b>\n━━━━━━━━━━━━━━━━━━\nকপি করে পূরণ করুন:\n\n<code>{fmt}</code>"
    
    if mode == "EMERGENCY WORK": 
        txt += "\n\n(স্ক্রিনশট বাধ্যতামূলক)"
        
    msg = bot.send_message(call.message.chat.id, txt)
    bot.register_next_step_handler(msg, lambda m: save_leave(m, mode))

def save_leave(message, mode):
    if is_cmd(message): return
    
    if mode == "EMERGENCY WORK" and not message.photo:
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া সাবমিট হবে না।")
    
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.photo else message.text)
    
    report = f"🩺 <b>{mode}</b>\n👤 {name}\n📢 {ADMIN_MENTION}\n📝 {cap}"
    
    try:
        if message.photo: 
            bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_LEAVE)
        else: 
            bot.send_message(ADMIN_GROUP_ID, report, message_thread_id=TOPIC_LEAVE)
            
        bot.send_message(message.chat.id, "✅ অ্যাডমিনকে জানানো হয়েছে।")
    except:
        bot.send_message(message.chat.id, "❌ এরর হয়েছে।")

# =======================================================
# 👑 ৬. অ্যাডমিন প্যানেল (Admin Panel & Controls)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_menu(message):
    if not is_admin(message.from_user): return
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📋 রিপোর্ট চেক", callback_data="adm_check"),
        types.InlineKeyboardButton("🏆 Best Performer ঘোষণা", callback_data="adm_best"),
        types.InlineKeyboardButton("👤 ইউজার ম্যানেজমেন্ট", callback_data="adm_manage"),
        types.InlineKeyboardButton("📢 প্রমোশন মেসেজ", callback_data="adm_promo"),
        types.InlineKeyboardButton("💬 মেনশন মেসেজ (নতুন)", callback_data="adm_mention")
    )
    bot.send_message(message.chat.id, "👑 <b>অ্যাডমিন কন্ট্রোল প্যানেল:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def handle_adm_callback(call):
    if not is_admin(call.from_user): return
    
    if call.data == "adm_mention":
        # মেনশন মেসেজ অপশন
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM users")
        users = cursor.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for u in users: 
            kb.add(types.InlineKeyboardButton(u[1], callback_data=f"mnt_{u[0]}"))
            
        bot.edit_message_text("💬 কাকে মেনশন করতে চান?", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_best":
        msg = bot.send_message(call.message.chat.id, "🏆 আজকের সেরা পারফর্মারের নাম ও ডিটেইলস লিখুন (ছবিসহ দিতে পারেন):")
        bot.register_next_step_handler(msg, broadcast_best)
        
    elif call.data == "adm_promo":
        msg = bot.send_message(call.message.chat.id, "📢 প্রমোশন মেসেজটি লিখুন (ছবিসহ দিতে পারেন):")
        bot.register_next_step_handler(msg, broadcast_promo)
        
    elif call.data == "adm_manage":
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM users")
        users = cursor.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for u in users: 
            kb.add(types.InlineKeyboardButton(f"❌ Remove: {u[1]}", callback_data=f"del_{u[0]}"))
            
        bot.edit_message_text("👤 ইউজার রিমুভ করুন:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_check":
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, name FROM users")
        users = cursor.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for u in users: 
            kb.add(types.InlineKeyboardButton(u[1], callback_data=f"rpt_{u[0]}"))
            
        bot.edit_message_text("📊 কার রিপোর্ট চেক করবেন?", call.message.chat.id, call.message.message_id, reply_markup=kb)

# --- নতুন মেনশন মেসেজ এর ফাংশন ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("mnt_"))
def mnt_step_2(call):
    uid = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "💬 ইউজারকে যা বলতে চান সেটি লিখুন (ছবিসহ দিতে পারেন):")
    bot.register_next_step_handler(msg, lambda m: send_mnt(m, uid))

def send_mnt(message, uid):
    if is_cmd(message): return
    txt = f"📩 <b>অ্যাডমিন আপনাকে মেনশন করেছে:</b>\n\n{clean_text(message.caption if message.photo else message.text)}"
    try:
        if message.photo: 
            bot.send_photo(uid, message.photo[-1].file_id, caption=txt)
        else: 
            bot.send_message(uid, txt)
        bot.send_message(message.chat.id, "✅ মেনশন মেসেজ সফলভাবে পাঠানো হয়েছে।")
    except: 
        bot.send_message(message.chat.id, "❌ পাঠানো যায়নি।")

# --- বেস্ট পারফর্মার এবং প্রমোশন ব্রডকাস্ট ---
def broadcast_best(message):
    if is_cmd(message): return
    txt = f"🌟 <b>সেরা পারফর্মার!</b> 🌟\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.caption if message.photo else message.text)}"
    send_to_all(txt, message.photo)

def broadcast_promo(message):
    if is_cmd(message): return
    txt = f"📢 <b>অ্যাডমিন নোটিশ:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.caption if message.photo else message.text)}"
    send_to_all(txt, message.photo)

def send_to_all(txt, photo=None):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    for u in users:
        try:
            if photo: 
                bot.send_photo(u[0], photo[-1].file_id, caption=txt)
            else: 
                bot.send_message(u[0], txt)
        except: 
            pass

# --- ইউজার রিমুভ ফাংশন ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def del_u(call):
    uid = call.data.split("_")[1]
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id=%s", (uid,))
    conn.commit()
    conn.close()
    bot.edit_message_text("✅ ইউজার রিমুভড।", call.message.chat.id, call.message.message_id)

# --- রিপোর্ট চেক ফাংশন ---
@bot.callback_query_handler(func=lambda c: c.data.startswith("rpt_"))
def rpt_range(call):
    uid = call.data.split("_")[1]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("২৪ ঘন্টা", callback_data=f"dr_{uid}_1"), 
        types.InlineKeyboardButton("৭ দিন", callback_data=f"dr_{uid}_7"), 
        types.InlineKeyboardButton("১৫ দিন", callback_data=f"dr_{uid}_15"), 
        types.InlineKeyboardButton("৩০ দিন", callback_data=f"dr_{uid}_30")
    )
    bot.edit_message_text("⏳ দিন সিলেক্ট করুন:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dr_"))
def rpt_final(call):
    parts = call.data.split("_")
    uid = int(parts[1])
    days = int(parts[2])
    
    target = (bd_time() - timedelta(days=days-1)).strftime("%Y-%m-%d")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE user_id=%s", (uid,))
    name = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(total_seconds),0) FROM work_hours WHERE user_id=%s AND date >= %s", (uid, target))
    sec = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(calls_h),0), COALESCE(SUM(nsu_h),0), COUNT(*) FROM hourly_stats WHERE user_id=%s AND date >= %s", (uid, target))
    st = cursor.fetchone()
    conn.close()
    
    h = sec // 3600
    m = (sec % 3600) // 60
    
    report_text = f"📊 <b>Report: {name}</b>\n━━━━━━━━━━━━━━━━━━\n⏳ মোট কাজ: {h} ঘণ্টা {m} মিনিট\n📑 Hourly সাবমিট: {st[2]} বার\n📞 মোট Calls: {st[0]} | 📉 মোট NSU: {st[1]}"
    bot.edit_message_text(report_text, call.message.chat.id, call.message.message_id)

# =======================================================
# ⏰ অটোমেশন (Alerts, Greetings and Reminders)
# =======================================================
def automation():
    best_alert = False
    greet = {"m": False, "a": False, "e": False}
    
    while True:
        try:
            now = bd_time()
            
            # 🔔 ১. সকাল ৯ টায় বেস্ট পারফর্মার অ্যালার্ট
            if now.hour == 9 and now.minute == 0 and not best_alert:
                bot.send_message(ADMIN_GROUP_ID, f"🔔 {ADMIN_MENTION} আজকের <b>Best Performer</b> ঘোষণা করার সময় হয়েছে।")
                best_alert = True
                
            if now.hour == 0: 
                best_alert = False

            # ☀️ ২. প্রতিদিনের শুভেচ্ছা বার্তা (সকাল, দুপুর, সন্ধ্যা)
            if now.hour == 8 and not greet["m"]:
                send_to_all("☀️ <b>শুভ সকাল!</b>\nকাজে মন দিন এবং আজকের লক্ষ্য পূরণ করুন। 🚀")
                greet["m"] = True
                
            if now.hour == 14 and not greet["a"]:
                send_to_all("🌤️ <b>শুভ দুপুর!</b>\nসাফল্যের জন্য আপনার চেষ্টাই যথেষ্ট। এগিয়ে যান! 💪")
                greet["a"] = True
                
            if now.hour == 18 and not greet["e"]:
                send_to_all("🌆 <b>শুভ সন্ধ্যা!</b>\nপেশাদারিত্বের সাথে আপনার পরিশ্রম চালিয়ে যান। ✨")
                greet["e"] = True
                
            if now.hour == 0: 
                greet = {"m": False, "a": False, "e": False}

            # 🔔 ৩. ৫০ মিনিট বিরতি ও রাত ১০ টা ডিউটি শেষ অ্যালার্ট
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, status, last_break_time, start_time FROM attendance")
            
            for u, s, lb, st in cursor.fetchall():
                
                # বিরতি অ্যালার্ট (৫০ মিনিট)
                if s == 'break' and lb:
                    diff = (now - datetime.strptime(lb, "%Y-%m-%d %H:%M:%S")).total_seconds()
                    if 3000 <= diff <= 3060: # 50 minutes window
                        try:
                            bot.send_message(u, "🔔 <b>বিরতি সংকেত:</b>\nআপনার ৫০ মিনিট পূর্ণ হয়েছে। এবার কাজে ফেরার সময় হয়েছে। 😊")
                        except: pass
                
                # রাত ১০ টায় ডিউটি শেষ অ্যালার্ট (যারা সকাল ১০ টায় শুরু করেছে)
                if s == 'working' and st and now.hour == 22 and now.minute == 0:
                    st_dt = datetime.strptime(st, "%Y-%m-%d %H:%M:%S")
                    
                    if st_dt.hour == 10: # যদি সকাল ১০টায় শুরু করে থাকে
                        is_adm = False
                        try:
                            m_stat = bot.get_chat_member(ADMIN_GROUP_ID, u).status
                            if m_stat in ['administrator', 'creator']: 
                                is_adm = True
                        except: pass
                        
                        if not is_adm:
                            try:
                                bot.send_message(u, "📢 <b>ডিউটি অ্যালার্ট:</b>\nআপনার ডিউটি সময় শেষ হয়েছে। দয়া করে শেষ Hourly Report দিয়ে ডিউটি শেষ করুন।")
                            except: pass
                            
            conn.close()
            time.sleep(60)
            
        except Exception as e: 
            print("Automation Error:", e)
            time.sleep(60)

# অটোমেশন ব্যাকগ্রাউন্ডে চালু করা হলো
threading.Thread(target=automation, daemon=True).start()

# =======================================================
# 🌐 ফ্লাস্ক সার্ভার এবং বট রানার (Flask Keep-Alive & Runner)
# =======================================================
app = Flask(__name__)

@app.route('/')
def home(): 
    return "🤖 Bot is Online with Cloud DB and Full Expanded Format!"

def run_bot():
    print("🚀 Bot is Online!")
    bot.remove_webhook()
    while True:
        try: 
            bot.infinity_polling(timeout=20, skip_pending=True)
        except Exception as e: 
            print("Polling Error:", e)
            time.sleep(5)

# বটকে আলাদা থ্রেডে চালু করা
threading.Thread(target=run_bot, daemon=True).start()

# মেইন থ্রেডে ফ্লাস্ক চালানো
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
