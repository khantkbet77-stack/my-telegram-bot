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

# অ্যাডমিন লিস্ট (এদের জন্য ওয়ার্নিং যাবে না)
ALLOWED_ADMINS = ['bdhasan09', 'alexbd96', 'aminal041']
ADMIN_MENTION = "@AlexBD96"

# টপিক আইডি 
TOPIC_PAYMENT = 3       
TOPIC_ATTENDANCE = 10   
TOPIC_RECHARGE = 13     
TOPIC_HOURLY = 88       
TOPIC_LEAVE = 405       

DB_URL = "postgresql://neondb_owner:npg_Efms7N5AzDZx@ep-fragrant-shape-aou3wk2j.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# =======================================================
# 🛡️ প্রয়োজনীয় ফাংশন সমূহ
# =======================================================
def get_conn():
    return psycopg2.connect(DB_URL)

def bd_time():
    return datetime.utcnow() + timedelta(hours=6)

def is_admin(user):
    if not user or not user.username: 
        return False
    return user.username.lower() in ALLOWED_ADMINS

def clean_text(text):
    if not text: 
        return "N/A"
    return text.replace("<", "").replace(">", "").replace("&", "and")

def is_cmd(message):
    btns = ["/start", "/menu", "📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন", "⏱️ Daily Attendance", "📱 Recharges", "🩺 SL-OFF-issue", "👑 Admin Panel"]
    if message.text in btns:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.process_new_messages([message])
        return True
    return False

def get_user_name(user_id):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id = %s", (user_id,))
        res = cursor.fetchone()
        conn.close()
        if res:
            return res[0]
        return "Unknown User"
    except: 
        return "Unknown User"

# =======================================================
# 🗄️ ডাটাবেস সেটআপ
# =======================================================
def setup_db():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT, username TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id BIGINT PRIMARY KEY, status TEXT, start_time TEXT, last_report_time TEXT, last_break_time TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS work_hours (user_id BIGINT, date TEXT, total_seconds INTEGER DEFAULT 0, UNIQUE(user_id, date))")
        cursor.execute("CREATE TABLE IF NOT EXISTS message_map (admin_msg_id BIGINT PRIMARY KEY, user_id BIGINT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS hourly_stats (id SERIAL PRIMARY KEY, user_id BIGINT, date TEXT, time TEXT, calls_h INTEGER, nsu_h INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports_log (user_id BIGINT, date TEXT, time TEXT, log TEXT)")
        conn.commit()
        conn.close()
    except Exception as e: 
        print("DB Setup Error:", e)

setup_db()

# =======================================================
# 🎛️ মেনু ও রেজিস্ট্রেশন
# =======================================================
def main_menu(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন")
    markup.add("⏱️ Daily Attendance", "📱 Recharges")
    markup.add("🩺 SL-OFF-issue")
    if is_admin(user): 
        markup.add("👑 Admin Panel")
    return markup

@bot.message_handler(commands=['start', 'menu'])
def start(message):
    name = get_user_name(message.chat.id)
    if name != "Unknown User":
        bot.send_message(message.chat.id, f"👇 <b>আপনার মেনু:</b>", reply_markup=main_menu(message.from_user))
    else:
        msg = bot.send_message(message.chat.id, "👋 <b>স্বাগতম! বটটি আপডেট করা হয়েছে।</b>\nসিস্টেম ব্যবহারের জন্য আপনার <b>পুরো নাম</b> লিখে সেন্ড করুন।")
        bot.register_next_step_handler(msg, register)

def register(message):
    if is_cmd(message): 
        return
        
    clean_name = clean_text(message.text)
    username = message.from_user.username.lower() if message.from_user.username else ""
    
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name, username = EXCLUDED.username", (message.chat.id, clean_name, username))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🎊 রেজিস্ট্রেশন সফল! স্বাগতম <b>{clean_name}</b>।", reply_markup=main_menu(message.from_user))
    except: 
        bot.send_message(message.chat.id, "❌ রেজিস্ট্রেশনে সমস্যা হয়েছে।")

# =======================================================
# ✅ অ্যাকশন বাটন (Approve / Reject / Work)
# =======================================================
def get_action_buttons(uid, show_work=True):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"act_app_{uid}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"act_rej_{uid}")
    )
    if show_work:
        kb.add(types.InlineKeyboardButton("⚙️ Work", callback_data=f"act_wrk_{uid}"))
    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith('act_'))
def handle_action_buttons(call):
    if not is_admin(call.from_user): 
        return bot.answer_callback_query(call.id, "⛔ অনুমতি নেই!")
        
    parts = call.data.split('_')
    action = parts[1]
    uid = int(parts[2])
    admin_name = call.from_user.first_name
    msg = call.message
    
    try:
        if action == 'wrk':
            new_kb = get_action_buttons(uid, show_work=False)
            status_text = "\n\n⚙️ <b>Status:</b> <i>Working on it...</i>"
            
            if msg.content_type == 'photo': 
                bot.edit_message_caption(caption=(msg.caption or "") + status_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=new_kb, parse_mode="HTML")
            else: 
                bot.edit_message_text(text=(msg.text or "") + status_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=new_kb, parse_mode="HTML")
                
        elif action == 'app':
            bot.send_message(uid, "✅ <b>আপনার রিকোয়েস্টটি অ্যাডমিন দ্বারা Approve করা হয়েছে!</b>")
            final_text = "\n\n✅ <b>Status:</b> Approved by " + admin_name
            
            if msg.content_type == 'photo': 
                bot.edit_message_caption(caption=(msg.caption or "").replace("Working on it...", "") + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
            else: 
                bot.edit_message_text(text=(msg.text or "").replace("Working on it...", "") + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
                
        elif action == 'rej':
            bot.send_message(uid, "❌ <b>আপনার রিকোয়েস্টটি অ্যাডমিন দ্বারা Reject করা হয়েছে।</b>")
            final_text = "\n\n❌ <b>Status:</b> Rejected by " + admin_name
            
            if msg.content_type == 'photo': 
                bot.edit_message_caption(caption=(msg.caption or "").replace("Working on it...", "") + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
            else: 
                bot.edit_message_text(text=(msg.text or "").replace("Working on it...", "") + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
    except: 
        bot.answer_callback_query(call.id, "অ্যাকশন এরর!")

# =======================================================
# ১. 📊 আওয়ারলি রিপোর্ট
# =======================================================
@bot.message_handler(func=lambda m: m.text == "📊 Hourly Report")
def hourly(message):
    name = get_user_name(message.chat.id)
    fmt = f"Caller Name: {name}\nTotal Call  (D): \nTotal NSU (D):\nTotal Call (H) :\nTotal NSU (H):"
    
    msg = bot.send_message(message.chat.id, f"📑 <b>নতুন আওয়ারলি রিপোর্ট</b>\n\n<code>{fmt}</code>\n\nস্ক্রিনশটসহ সাবমিট করুন।")
    bot.register_next_step_handler(msg, save_hourly)

def save_hourly(message):
    if is_cmd(message): 
        return
        
    if not message.photo: 
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট বাধ্যতামূলক।")
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption)
    
    calls_h = 0
    nsu_h = 0
    try:
        c_match = re.search(r"Total Call \(H\)[^\d]*(\d+)", cap, re.IGNORECASE)
        n_match = re.search(r"Total NSU \(H\)[^\d]*(\d+)", cap, re.IGNORECASE)
        if c_match: 
            calls_h = int(c_match.group(1))
        if n_match: 
            nsu_h = int(n_match.group(1))
    except: 
        pass
        
    now = bd_time()
    
    try:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=f"📊 <b>HOURLY REPORT</b>\n👤 {name}\n⏰ {now.strftime('%I:%M %p')}\n\n{cap}", message_thread_id=TOPIC_HOURLY)
        
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE attendance SET last_report_time = %s WHERE user_id = %s", (now.strftime("%Y-%m-%d %H:%M:%S"), message.chat.id))
        cursor.execute("INSERT INTO hourly_stats (user_id, date, time, calls_h, nsu_h) VALUES (%s, %s, %s, %s, %s)", (message.chat.id, now.strftime("%Y-%m-%d"), now.strftime('%I:%M %p'), calls_h, nsu_h))
        cursor.execute("INSERT INTO reports_log (user_id, date, time, log) VALUES (%s, %s, %s, %s)", (message.chat.id, now.strftime("%Y-%m-%d"), now.strftime('%I:%M %p'), cap))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ রিপোর্ট জমা হয়েছে।")
    except: 
        bot.send_message(message.chat.id, "❌ এরর হয়েছে।")

# =======================================================
# ২. 💳 ডিপোজিট/উত্তোলন
# =======================================================
@bot.message_handler(func=lambda m: m.text == "💳 ডিপোজিট/উত্তোলন")
def dep_with_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📥 ডিপোজিট", callback_data="req_dep"), 
        types.InlineKeyboardButton("📤 উত্তোলন", callback_data="req_with")
    )
    bot.send_message(message.chat.id, "💳 রিকুয়েস্ট ধরন সিলেক্ট করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['req_dep', 'req_with'])
def handle_dep_with(call):
    try: 
        bot.answer_callback_query(call.id)
    except: 
        pass
        
    is_dep = (call.data == "req_dep")
    
    if is_dep:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nট্রানজেকশন আইডি: \nনোট: "
    else:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nলেনদেন আইডি: \nঅ্যামাউন্ট: \nনোট: "
        
    msg = bot.send_message(call.message.chat.id, f"💳 {'ডিপোজিট' if is_dep else 'উত্তোলন'}\n\n<code>{fmt}</code>")
    bot.register_next_step_handler(msg, lambda m: save_transaction(m, "DEPOSIT" if is_dep else "WITHDRAWAL"))

def save_transaction(message, req_type):
    if is_cmd(message): 
        return
        
    if req_type == "DEPOSIT" and not message.photo: 
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট লাগবে।")
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.photo else message.text)
    
    report = f"💰 <b>{req_type} REQUEST</b>\n👤 User: {name}\n📢 <b>Admin:</b> {ADMIN_MENTION}\n📝 Details:\n{cap}"
    act_kb = get_action_buttons(message.chat.id)
    
    try:
        if message.photo: 
            bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, reply_markup=act_kb, message_thread_id=TOPIC_PAYMENT)
        else: 
            bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_PAYMENT)
            
        bot.send_message(message.chat.id, "✅ অ্যাডমিনকে রিকোয়েস্ট পাঠানো হয়েছে।")
    except: 
        bot.send_message(message.chat.id, "❌ এরর হয়েছে।")

# =======================================================
# ৩. ⏱️ এটেনডেন্স (সঠিক টাইম হিসাব)
# =======================================================
@bot.message_handler(func=lambda m: m.text == "⏱️ Daily Attendance")
def attend_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🟢 ডিউটি শুরু", callback_data="sw"), 
        types.InlineKeyboardButton("⏸️ বিরতি", callback_data="bw")
    )
    kb.add(types.InlineKeyboardButton("🔴 ডিউটি শেষ", callback_data="pw"))
    
    bot.send_message(message.chat.id, "⏱️ এটেনডেন্স প্যানেল", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['sw', 'bw', 'pw'])
def attend_call(call):
    try: 
        bot.answer_callback_query(call.id, "প্রসেস হচ্ছে...")
    except: 
        pass
        
    uid = call.message.chat.id
    name = get_user_name(uid)
    now = bd_time()
    
    t_str = now.strftime("%Y-%m-%d %H:%M:%S")
    d_str = now.strftime("%Y-%m-%d")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (user_id, status) VALUES (%s, 'stopped') ON CONFLICT (user_id) DO NOTHING", (uid,))
    cursor.execute("SELECT status, start_time FROM attendance WHERE user_id=%s", (uid,))
    row = cursor.fetchone()
    
    c_status = row[0]
    s_str = row[1]
    
    if call.data == 'sw':
        if c_status == 'working':
            bot.send_message(uid, "⚠️ আপনি ইতিমধ্যেই কাজে অ্যাক্টিভ আছেন!")
        else:
            msg = "🟢 <b>Duty Resumed (ফিরলো)</b>" if c_status == 'break' else "🟢 <b>Duty Started</b>"
            cursor.execute("UPDATE attendance SET status='working', start_time=%s, last_report_time=%s WHERE user_id=%s", (t_str, t_str, uid))
            bot.send_message(ADMIN_GROUP_ID, f"{msg}\n👤 {name}\n⏰ {now.strftime('%I:%M %p')}", message_thread_id=TOPIC_ATTENDANCE)
            bot.edit_message_text("✅ ডিউটি শুরু হয়েছে।", uid, call.message.message_id)
            
    elif call.data == 'bw':
        if c_status == 'working':
            try:
                st = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
                sec = max(int((now - st).total_seconds()), 0)
                cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (%s, %s, 0) ON CONFLICT (user_id, date) DO NOTHING", (uid, d_str))
                cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + %s WHERE user_id=%s AND date=%s", (sec, uid, d_str))
            except: 
                pass
                
            cursor.execute("UPDATE attendance SET status='break', last_break_time=%s WHERE user_id=%s", (t_str, uid))
            bot.send_message(ADMIN_GROUP_ID, f"⏸️ <b>Break Taken</b>\n👤 {name}\n⏰ {now.strftime('%I:%M %p')}", message_thread_id=TOPIC_ATTENDANCE)
            bot.edit_message_text("✅ বিরতি শুরু হয়েছে।", uid, call.message.message_id)
            
    elif call.data == 'pw':
        if c_status == 'working':
            try:
                st = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
                sec = max(int((now - st).total_seconds()), 0)
                cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (%s, %s, 0) ON CONFLICT (user_id, date) DO NOTHING", (uid, d_str))
                cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + %s WHERE user_id=%s AND date=%s", (sec, uid, d_str))
            except: 
                pass
                
        cursor.execute("UPDATE attendance SET status='stopped' WHERE user_id=%s", (uid,))
        bot.send_message(ADMIN_GROUP_ID, f"🔴 <b>Duty Ended</b>\n👤 {name}\n⏰ {now.strftime('%I:%M %p')}", message_thread_id=TOPIC_ATTENDANCE)
        bot.edit_message_text("✅ ডিউটি শেষ হয়েছে।", uid, call.message.message_id)
        
    conn.commit()
    conn.close()

# =======================================================
# ৪. 📱 Recharges / ৫. SL-OFF
# =======================================================
@bot.message_handler(func=lambda m: m.text == "📱 Recharges")
def recharge_app(message):
    fmt = "তারিখ: \nপেমেন্ট সিস্টেম: \nএমাউন্টও: "
    msg = bot.send_message(message.chat.id, f"📱 <b>Recharge</b>\n\n<code>{fmt}</code>\n\nস্ক্রিনশটসহ দিন।")
    bot.register_next_step_handler(msg, save_recharge)

def save_recharge(message):
    if is_cmd(message) or not message.photo: 
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট বাধ্যতামূলক।")
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption)
    act_kb = get_action_buttons(message.chat.id)
    
    try:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=f"📱 <b>RECHARGE</b>\n👤 {name}\n📝 {cap}", reply_markup=act_kb, message_thread_id=TOPIC_RECHARGE)
        bot.send_message(message.chat.id, "✅ পাঠানো হয়েছে।")
    except: 
        pass

@bot.message_handler(func=lambda m: m.text == "🩺 SL-OFF-issue")
def leave_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🤒 অসুস্থ ছুটি", callback_data="lv_sick"), 
        types.InlineKeyboardButton("⏳ অতিরিক্ত বিরতি সময়", callback_data="lv_extra"), 
        types.InlineKeyboardButton("🆘 ইমারজেন্সি কাজ", callback_data="lv_emg")
    )
    bot.send_message(message.chat.id, "🩺 ধরন সিলেক্ট করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('lv_'))
def handle_leave(call):
    if call.data == "lv_sick": 
        f = "তারিখ: \nবিস্তারিত: \nদিন: "
        m = "SICK LEAVE"
    elif call.data == "lv_extra": 
        f = "বিরতি শুরু: \nবিরতি শেষ: \nমোট সময়: "
        m = "EXTRA BREAK"
    else: 
        f = "তারিখ: \nকারণ: \nডকুমেন্টস: "
        m = "EMERGENCY WORK"
        
    msg = bot.send_message(call.message.chat.id, f"📝 {m}\n\n<code>{f}</code>" + ("\n(স্ক্রিনশট বাধ্যতামূলক)" if m == "EMERGENCY WORK" else ""))
    bot.register_next_step_handler(msg, lambda ms: save_leave(ms, m))

def save_leave(message, mode):
    if is_cmd(message): 
        return
        
    if mode == "EMERGENCY WORK" and not message.photo: 
        return bot.send_message(message.chat.id, "❌ স্ক্রিনশট লাগবে।")
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.photo else message.text)
    act_kb = get_action_buttons(message.chat.id)
    
    report = f"🩺 <b>{mode}</b>\n👤 {name}\n📢 {ADMIN_MENTION}\n📝 {cap}"
    
    try:
        if message.photo: 
            bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE)
        else: 
            bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE)
            
        bot.send_message(message.chat.id, "✅ পাঠানো হয়েছে।")
    except: 
        pass

# =======================================================
# 👑 অ্যাডমিন প্যানেল ও প্রমোশন
# =======================================================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_menu(message):
    if not is_admin(message.from_user): 
        return
        
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📋 রিপোর্ট চেক", callback_data="adm_check"), 
        types.InlineKeyboardButton("🏆 Best Performer ঘোষণা", callback_data="adm_best"), 
        types.InlineKeyboardButton("👤 ইউজার ম্যানেজমেন্ট", callback_data="adm_manage"), 
        types.InlineKeyboardButton("📢 প্রমোশন মেসেজ", callback_data="adm_promo"), 
        types.InlineKeyboardButton("💬 মেনশন মেসেজ", callback_data="adm_mention"), 
        types.InlineKeyboardButton("📢 আপডেট নোটিশ পাঠান", callback_data="adm_upd_not")
    )
    bot.send_message(message.chat.id, "👑 অ্যাডমিন প্যানেল:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def handle_adm_callback(call):
    if not is_admin(call.from_user): 
        return
        
    if call.data == "adm_upd_not":
        msg = bot.send_message(call.message.chat.id, "📢 আপডেট নোটিশটি লিখুন:")
        bot.register_next_step_handler(msg, broadcast_promo)
        
    elif call.data == "adm_mention":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        u = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in u: 
            kb.add(types.InlineKeyboardButton(x[1], callback_data=f"mnt_{x[0]}"))
            
        bot.edit_message_text("💬 কাকে মেনশন করবেন?", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_best":
        msg = bot.send_message(call.message.chat.id, "🏆 <b>গতকালকের</b> সেরা পারফর্মার লিখুন (ছবিসহ দিতে পারেন):")
        bot.register_next_step_handler(msg, broadcast_best)
        
    elif call.data == "adm_promo":
        msg = bot.send_message(call.message.chat.id, "📢 প্রমোশন মেসেজটি লিখুন:")
        bot.register_next_step_handler(msg, broadcast_promo)
        
    elif call.data == "adm_manage":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        u = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in u: 
            kb.add(types.InlineKeyboardButton(f"❌ Remove: {x[1]}", callback_data=f"del_{x[0]}"))
            
        bot.edit_message_text("👤 ইউজার রিমুভ:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_check":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        u = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in u: 
            kb.add(types.InlineKeyboardButton(x[1], callback_data=f"rpt_{x[0]}"))
            
        bot.edit_message_text("📊 রিপোর্ট চেক:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mnt_"))
def mnt_step_2(call):
    uid = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "💬 মেনশন মেসেজ লিখুন (ছবিসহ হতে পারে):")
    bot.register_next_step_handler(msg, lambda m: send_mnt(m, uid))

def send_mnt(message, uid):
    if is_cmd(message): 
        return
        
    txt = f"📩 <b>অ্যাডমিন আপনাকে মেনশন করেছে:</b>\n\n{clean_text(message.caption if message.photo else message.text)}"
    
    try:
        if message.photo: 
            bot.send_photo(uid, message.photo[-1].file_id, caption=txt)
        else: 
            bot.send_message(uid, txt)
            
        bot.send_message(message.chat.id, "✅ মেনশন পাঠানো হয়েছে।")
    except: 
        pass

def broadcast_best(message):
    if is_cmd(message): 
        return
        
    txt = f"🌟 <b>সেরা পারফর্মার!</b> 🌟\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.caption if message.photo else message.text)}"
    send_to_all(txt, message.photo)

def broadcast_promo(message):
    if is_cmd(message): 
        return
        
    txt = f"📢 <b>নোটিশ:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.caption if message.photo else message.text)}"
    send_to_all(txt, message.photo)

def send_to_all(txt, photo=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users")
    u = cur.fetchall()
    conn.close()
    
    for x in u:
        try:
            if photo: 
                bot.send_photo(x[0], photo[-1].file_id, caption=txt)
            else: 
                bot.send_message(x[0], txt)
        except: 
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def del_u(call):
    uid = call.data.split("_")[1]
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))
    conn.commit()
    conn.close()
    
    bot.edit_message_text("✅ ইউজার রিমুভড।", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rpt_"))
def rpt_range(call):
    uid = call.data.split("_")[1]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("২৪ ঘণ্টা", callback_data=f"dr_{uid}_1"), 
        types.InlineKeyboardButton("৭ দিন", callback_data=f"dr_{uid}_7"), 
        types.InlineKeyboardButton("১৫ দিন", callback_data=f"dr_{uid}_15"), 
        types.InlineKeyboardButton("৩০ দিন", callback_data=f"dr_{uid}_30")
    )
    bot.edit_message_text("⏳ সময় নির্বাচন করুন:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dr_"))
def rpt_final(call):
    p = call.data.split("_")
    uid = int(p[1])
    days = int(p[2])
    
    target = (bd_time() - timedelta(days=days-1)).strftime("%Y-%m-%d")
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT name FROM users WHERE user_id=%s", (uid,))
    n = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(total_seconds),0) FROM work_hours WHERE user_id=%s AND date >= %s", (uid, target))
    s = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(calls_h),0), COALESCE(SUM(nsu_h),0), COUNT(*) FROM hourly_stats WHERE user_id=%s AND date >= %s", (uid, target))
    st = cur.fetchone()
    
    conn.close()
    
    h = s // 3600
    m = (s % 3600) // 60
    
    bot.edit_message_text(f"📊 <b>Report: {n}</b>\n⏳ মোট কাজ: {h} ঘণ্টা {m} মিনিট\n📑 Hourly: {st[2]} বার\n📞 Calls: {st[0]} | 📉 NSU: {st[1]}", call.message.chat.id, call.message.message_id)

# =======================================================
# ⏰ অটোমেশন ও ওয়ার্নিং সিস্টেম
# =======================================================
def automation():
    best_alert = False
    greet = {"m": False, "a": False, "e": False}
    
    while True:
        try:
            now = bd_time()
            
            # সকাল ৯টায় বেস্ট পারফর্মার অ্যালার্ট
            if now.hour == 9 and now.minute == 0 and not best_alert:
                bot.send_message(ADMIN_GROUP_ID, f"🔔 {ADMIN_MENTION} <b>গতকালকের Best Performer</b> ঘোষণার সময় হয়েছে।")
                best_alert = True
                
            if now.hour == 0: 
                best_alert = False
                greet = {"m": False, "a": False, "e": False}

            # শুভেচ্ছা বার্তা
            if now.hour == 8 and not greet["m"]: 
                send_to_all("☀️ <b>শুভ সকাল!</b>\nকাজে মন দিন এবং আজকের লক্ষ্য পূরণ করুন। 🚀")
                greet["m"] = True
                
            if now.hour == 14 and not greet["a"]: 
                send_to_all("🌤️ <b>শুভ দুপুর!</b>\nসাফল্যের জন্য আপনার চেষ্টাই যথেষ্ট। এগিয়ে যান! 💪")
                greet["a"] = True
                
            if now.hour == 18 and not greet["e"]: 
                send_to_all("🌆 <b>শুভ সন্ধ্যা!</b>\nপেশাদারিত্বের সাথে পরিশ্রম চালিয়ে যান। ✨")
                greet["e"] = True

            # ওয়ার্নিং ও অ্যালার্ট
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT a.user_id, a.status, a.last_break_time, a.start_time, a.last_report_time, u.name, u.username FROM attendance a JOIN users u ON a.user_id = u.user_id")
            rows = cur.fetchall()
            
            for u, s, lb, st, lr, name, username in rows:
                is_u_admin = username is not None and username.lower() in ALLOWED_ADMINS
                
                # ওয়ার্নিং শুধু নন-অ্যাডমিনদের জন্য
                if not is_u_admin:
                    if s == 'break' and lb:
                        diff = (now - datetime.strptime(lb, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        
                        if 3000 <= diff <= 3060: 
                            bot.send_message(u, "🔔 বিরতির ৫০ মিনিট পূর্ণ হয়েছে। কাজে ফেরার সময় হয়েছে। 😊")
                        if 3600 <= diff <= 3660: 
                            bot.send_message(ADMIN_GROUP_ID, f"⚠️ <b>Warning:</b> {name} ১ ঘণ্টার বেশি সময় ধরে বিরতিতে!")
                            
                    if s == 'working' and lr:
                        if (now - datetime.strptime(lr, "%Y-%m-%d %H:%M:%S")).total_seconds() >= 4500: # ১ ঘণ্টা ১৫ মিনিট
                            bot.send_message(ADMIN_GROUP_ID, f"⚠️ <b>Warning:</b> {name} ১ ঘণ্টা ১৫ মিনিট ধরে রিপোর্ট দেননি!")
                            
                    if s == 'working' and st and now.hour == 22 and now.minute == 0:
                        if datetime.strptime(st, "%Y-%m-%d %H:%M:%S").hour == 10: 
                            bot.send_message(u, "📢 সময় শেষ! শেষ রিপোর্ট দিয়ে ডিউটি শেষ করুন।")
                            
            conn.close()
            time.sleep(60)
        except: 
            time.sleep(60)

threading.Thread(target=automation, daemon=True).start()

# =======================================================
# 🌐 রানার
# =======================================================
app = Flask(__name__)

@app.route('/')
def home(): 
    return "🤖 Bot is Online with Neon DB & Admin Protection!"

def run_bot():
    bot.remove_webhook()
    while True:
        try: 
            bot.infinity_polling(timeout=20, skip_pending=True)
        except: 
            time.sleep(5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
