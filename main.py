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

# অ্যাডমিন লিস্ট (এদেরকে কোনো ওয়ার্নিং বা রিমাইন্ডার দেওয়া হবে না)
ALLOWED_ADMINS = ['aminal041', 'bdhasan09', 'alexbd96']
ADMIN_MENTION = "@AlexBD96"

# টপিক আইডি সমূহ
TOPIC_PAYMENT = 3       
TOPIC_ATTENDANCE = 10   
TOPIC_RECHARGE = 13     
TOPIC_HOURLY = 88       
TOPIC_LEAVE = 405       

# ক্লাউড ডাটাবেস ইউআরএল (Neon DB)
DB_URL = "postgresql://neondb_owner:npg_Efms7N5AzDZx@ep-fragrant-shape-aou3wk2j.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# =======================================================
# 🛡️ প্রয়োজনীয় ফাংশন সমূহ (Helper Functions)
# =======================================================
def get_conn():
    """ডাটাবেস কানেকশন তৈরির ফাংশন"""
    return psycopg2.connect(DB_URL)

def bd_time():
    """বাংলাদেশ সময় (UTC+6) বের করার ফাংশন"""
    return datetime.utcnow() + timedelta(hours=6)

def is_admin_user(username):
    """ইউজারনেম দিয়ে অ্যাডমিন যাচাই (ডাটাবেস থেকে)"""
    if not username:
        return False
    return username.lower() in ALLOWED_ADMINS

def is_admin_obj(user):
    """টেলিগ্রাম ইউজার অবজেক্ট দিয়ে অ্যাডমিন যাচাই (লাইভ)"""
    if not user or not user.username:
        return False
    return user.username.lower() in ALLOWED_ADMINS

def clean_text(text):
    """টেক্সট ক্লিন করার ফাংশন"""
    if not text:
        return "N/A"
    return text.replace("<", "").replace(">", "").replace("&", "and")

def is_cmd(message):
    """চেক করবে মেসেজটি কি কোনো কমান্ড বা বাটন?"""
    btns = ["/start", "/menu", "📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন", "⏱️ Daily Attendance", "📱 Recharges", "🩺 SL-OFF-issue", "👑 Admin Panel"]
    
    if message.text in btns:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.process_new_messages([message])
        return True
    return False

def get_user_name(user_id):
    """ডাটাবেস থেকে ইউজারের নাম বের করা"""
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
    except Exception as e:
        return "Unknown User"

# =======================================================
# 🗄️ ডাটাবেস সেটআপ (Safe Setup)
# =======================================================
def setup_db():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # ইউজার টেবিল এবং কলাম তৈরি
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, name TEXT)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
        
        # অন্যান্য প্রয়োজনীয় টেবিল
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
    
    # শুধু অ্যাডমিনদের প্যানেল বাটন দেখাবে
    if is_admin_obj(user):
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
    except Exception as e:
        bot.send_message(message.chat.id, "❌ রেজিস্ট্রেশনে সমস্যা হয়েছে।")

# =======================================================
# ✅ অ্যাকশন বাটন লজিক (Approve / Reject / Work)
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
    if not is_admin_obj(call.from_user):
        bot.answer_callback_query(call.id, "⛔ অনুমতি নেই!")
        return
        
    parts = call.data.split('_')
    action = parts[1]
    uid = int(parts[2])
    admin_name = call.from_user.first_name
    msg = call.message
    
    # যে টপিকে ক্লিক করা হয়েছে, সেটার আইডি বের করা
    thread_id = msg.message_thread_id
    
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
            work_status_str = "\n\n⚙️ <b>Status:</b> <i>Working on it...</i>"
            
            if msg.content_type == 'photo':
                clean_caption = (msg.caption or "").replace(work_status_str, "")
                bot.edit_message_caption(caption=clean_caption + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
            else:
                clean_text_content = (msg.text or "").replace(work_status_str, "")
                bot.edit_message_text(text=clean_text_content + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
                
        elif action == 'rej':
            # রিজেক্ট করার কারণ চাওয়ার লজিক - এখন নির্দিষ্ট টপিকেই মেসেজ যাবে!
            prompt_msg = bot.send_message(
                call.message.chat.id, 
                f"⚠️ <b>{admin_name}</b>, দয়া করে রিকোয়েস্টটি রিজেক্ট করার কারণ লিখে সেন্ড করুন (না দিতে চাইলে 'Skip' লিখুন):",
                message_thread_id=thread_id
            )
            bot.register_next_step_handler(prompt_msg, process_rejection_reason, uid, msg, admin_name, prompt_msg.message_id)
            
    except Exception as e:
        bot.answer_callback_query(call.id, "অ্যাকশন আপডেট করতে সমস্যা হয়েছে!")

def process_rejection_reason(message, uid, original_msg, admin_name, prompt_msg_id):
    if is_cmd(message): 
        return
        
    reason = clean_text(message.text)
    user_msg = "❌ <b>আপনার রিকোয়েস্টটি অ্যাডমিন দ্বারা Reject করা হয়েছে।</b>"
    
    # মেইন রিকোয়েস্টের নিচে যুক্ত করার জন্য নোট এবং স্ট্যাটাস
    final_appended_text = ""
    
    # অ্যাডমিন যদি Skip না লেখে, তবেই কারণটা যুক্ত হবে
    if reason.lower() not in ['skip', 'na', 'n/a', 'no']:
        user_msg += f"\n📝 <b>কারণ:</b> {reason}"
        # গ্রুপের জন্য ছোট করে নোট (Status এর ওপরে থাকবে)
        final_appended_text += f"\n\n📌 <i>Note: {reason}</i>"
        
    # স্ট্যাটাস লাইনটি সবার শেষে যুক্ত হবে
    final_appended_text += f"\n\n❌ <b>Status:</b> Rejected by {admin_name}"
        
    # ইউজারকে পার্সোনাল মেসেজ পাঠানো
    try:
        bot.send_message(uid, user_msg)
    except Exception as e:
        pass
        
    # অ্যাডমিন গ্রুপের মেইন মেসেজ আপডেট করা
    try:
        work_status_str = "\n\n⚙️ <b>Status:</b> <i>Working on it...</i>"
        
        if original_msg.content_type == 'photo':
            # আগের 'Working on it' লেখাটা মুছে নতুন নোট এবং স্ট্যাটাস বসানো
            clean_caption = (original_msg.caption or "").replace(work_status_str, "")
            bot.edit_message_caption(caption=clean_caption + final_appended_text, chat_id=original_msg.chat.id, message_id=original_msg.message_id, reply_markup=None, parse_mode="HTML")
        else:
            clean_text_content = (original_msg.text or "").replace(work_status_str, "")
            bot.edit_message_text(text=clean_text_content + final_appended_text, chat_id=original_msg.chat.id, message_id=original_msg.message_id, reply_markup=None, parse_mode="HTML")
    except Exception as e:
        pass
        
    # গ্রুপ পরিষ্কার রাখতে অ্যাডমিনের রিপ্লাই এবং বটের প্রশ্ন ডিলিট করে দেওয়া
    try:
        bot.delete_message(message.chat.id, message.message_id)
        bot.delete_message(message.chat.id, prompt_msg_id)
    except Exception as e:
        pass
        
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
        bot.send_message(message.chat.id, "❌ স্ক্রিনশট বাধ্যতামূলক।")
        return
        
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
    except Exception as e:
        pass
        
    now = bd_time()
    time_str = now.strftime('%I:%M %p')
    date_str = now.strftime("%Y-%m-%d")
    
    try:
        report_text = f"📊 <b>HOURLY REPORT</b>\n👤 {name}\n⏰ {time_str}\n\n{cap}"
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report_text, message_thread_id=TOPIC_HOURLY)
        
        conn = get_conn()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE attendance SET last_report_time = %s WHERE user_id = %s", (now.strftime("%Y-%m-%d %H:%M:%S"), message.chat.id))
        cursor.execute("INSERT INTO hourly_stats (user_id, date, time, calls_h, nsu_h) VALUES (%s, %s, %s, %s, %s)", (message.chat.id, date_str, time_str, calls_h, nsu_h))
        
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ আপনার রিপোর্ট জমা হয়েছে।")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ রিপোর্ট জমা দিতে সমস্যা হয়েছে।")

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
    except Exception as e:
        pass
        
    is_dep = (call.data == "req_dep")
    
    if is_dep:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nট্রানজেকশন আইডি: \nনোট: "
    else:
        fmt = "ইউজার নাম: \nমোবাইল নাম্বার: \nলেনদেন আইডি: \nঅ্যামাউন্ট: \nনোট: "
        
    title = "ডিপোজিট" if is_dep else "উত্তোলন"
    msg = bot.send_message(call.message.chat.id, f"💳 {title}\n\n<code>{fmt}</code>")
    bot.register_next_step_handler(msg, lambda m: save_transaction(m, "DEPOSIT" if is_dep else "WITHDRAWAL"))

def save_transaction(message, req_type):
    if is_cmd(message):
        return
        
    if req_type == "DEPOSIT" and not message.photo:
        bot.send_message(message.chat.id, "❌ ডিপোজিটের জন্য স্ক্রিনশট বাধ্যতামূলক।")
        return
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.photo else message.text)
    
    act_kb = get_action_buttons(message.chat.id)
    report = f"💰 <b>{req_type} REQUEST</b>\n👤 User: {name}\n📢 <b>Admin:</b> {ADMIN_MENTION}\n📝 Details:\n{cap}"
    
    try:
        if message.photo:
            bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, reply_markup=act_kb, message_thread_id=TOPIC_PAYMENT)
        else:
            bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_PAYMENT)
            
        bot.send_message(message.chat.id, "✅ অ্যাডমিনকে রিকোয়েস্ট পাঠানো হয়েছে।")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ রিকোয়েস্ট পাঠাতে সমস্যা হয়েছে।")

# =======================================================
# ৩. ⏱️ এটেনডেন্স (সঠিক লজিকসহ)
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
    except Exception as e:
        pass
        
    uid = call.message.chat.id
    name = get_user_name(uid)
    now = bd_time()
    
    t_str = now.strftime("%Y-%m-%d %H:%M:%S")
    d_str = now.strftime("%Y-%m-%d")
    disp_time = now.strftime('%I:%M %p')
    
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
            if c_status == 'break':
                msg_text = "🟢 <b>Duty Resumed (ফিরলো)</b>"
            else:
                msg_text = "🟢 <b>Duty Started</b>"
                
            cursor.execute("UPDATE attendance SET status='working', start_time=%s, last_report_time=%s WHERE user_id=%s", (t_str, t_str, uid))
            bot.send_message(ADMIN_GROUP_ID, f"{msg_text}\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
            bot.edit_message_text("✅ ডিউটি শুরু হয়েছে।", uid, call.message.message_id)
            
    elif call.data == 'bw':
        if c_status == 'break':
            bot.send_message(uid, "⚠️ আপনি ইতিমধ্যেই বিরতিতে আছেন!")
        elif c_status == 'stopped':
            bot.send_message(uid, "⚠️ আপনি এখনো ডিউটি শুরু করেননি!")
        else:
            try:
                st = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
                sec = max(int((now - st).total_seconds()), 0)
                
                cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (%s, %s, 0) ON CONFLICT (user_id, date) DO NOTHING", (uid, d_str))
                cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + %s WHERE user_id=%s AND date=%s", (sec, uid, d_str))
            except Exception as e:
                pass
                
            cursor.execute("UPDATE attendance SET status='break', last_break_time=%s WHERE user_id=%s", (t_str, uid))
            bot.send_message(ADMIN_GROUP_ID, f"⏸️ <b>Break Taken</b>\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
            bot.edit_message_text("✅ বিরতি শুরু হয়েছে।", uid, call.message.message_id)
            
    elif call.data == 'pw':
        if c_status == 'stopped':
            bot.send_message(uid, "⚠️ আপনার ডিউটি আগেই শেষ হয়েছে!")
        else:
            if c_status == 'working':
                try:
                    st = datetime.strptime(s_str, "%Y-%m-%d %H:%M:%S")
                    sec = max(int((now - st).total_seconds()), 0)
                    
                    cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (%s, %s, 0) ON CONFLICT (user_id, date) DO NOTHING", (uid, d_str))
                    cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + %s WHERE user_id=%s AND date=%s", (sec, uid, d_str))
                except Exception as e:
                    pass
                    
            cursor.execute("UPDATE attendance SET status='stopped' WHERE user_id=%s", (uid,))
            bot.send_message(ADMIN_GROUP_ID, f"🔴 <b>Duty Ended</b>\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
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
    if is_cmd(message):
        return
        
    if not message.photo:
        bot.send_message(message.chat.id, "❌ স্ক্রিনশট বাধ্যতামূলক।")
        return
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption)
    act_kb = get_action_buttons(message.chat.id)
    
    try:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=f"📱 <b>RECHARGE</b>\n👤 {name}\n📝 {cap}", reply_markup=act_kb, message_thread_id=TOPIC_RECHARGE)
        bot.send_message(message.chat.id, "✅ পাঠানো হয়েছে।")
    except Exception as e:
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
        fmt = "তারিখ: \nবিস্তারিত: \nদিন: "
        mode = "SICK LEAVE"
    elif call.data == "lv_extra":
        fmt = "বিরতি শুরু: \nবিরতি শেষ: \nমোট সময়: "
        mode = "EXTRA BREAK"
    else:
        fmt = "তারিখ: \nকারণ: \nডকুমেন্টস: "
        mode = "EMERGENCY WORK"
        
    txt = f"📝 {mode}\n\n<code>{fmt}</code>"
    
    if mode == "EMERGENCY WORK":
        txt += "\n(স্ক্রিনশট বাধ্যতামূলক)"
        
    msg = bot.send_message(call.message.chat.id, txt)
    bot.register_next_step_handler(msg, lambda ms: save_leave(ms, mode))

def save_leave(message, mode):
    if is_cmd(message):
        return
        
    if mode == "EMERGENCY WORK" and not message.photo:
        bot.send_message(message.chat.id, "❌ স্ক্রিনশট লাগবে।")
        return
        
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.photo else message.text)
    
    act_kb = get_action_buttons(message.chat.id)
    report = f"🩺 <b>{mode}</b>\n👤 {name}\n📢 {ADMIN_MENTION}\n📝 {cap}"
    
    try:
        if message.photo:
            bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE)
        else:
            bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE)
            
        bot.send_message(message.chat.id, "✅ অ্যাডমিনকে জানানো হয়েছে।")
    except Exception as e:
        pass

# =======================================================
# 👑 অ্যাডমিন প্যানেল
# =======================================================
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_menu(message):
    if not is_admin_obj(message.from_user):
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
    if not is_admin_obj(call.from_user):
        return
        
    if call.data == "adm_upd_not":
        msg = bot.send_message(call.message.chat.id, "📢 আপডেট নোটিশটি লিখুন:")
        bot.register_next_step_handler(msg, broadcast_promo)
        
    elif call.data == "adm_mention":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        users_list = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in users_list:
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
        users_list = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in users_list:
            kb.add(types.InlineKeyboardButton(f"❌ Remove: {x[1]}", callback_data=f"del_{x[0]}"))
            
        bot.edit_message_text("👤 ইউজার রিমুভ:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_check":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        users_list = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in users_list:
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
    except Exception as e:
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
    users_list = cur.fetchall()
    conn.close()
    
    for u in users_list:
        try:
            if photo:
                bot.send_photo(u[0], photo[-1].file_id, caption=txt)
            else:
                bot.send_message(u[0], txt)
        except Exception as e:
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
    parts = call.data.split("_")
    uid = int(parts[1])
    days = int(parts[2])
    
    target = (bd_time() - timedelta(days=days-1)).strftime("%Y-%m-%d")
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("SELECT name FROM users WHERE user_id=%s", (uid,))
    user_name = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(total_seconds),0) FROM work_hours WHERE user_id=%s AND date >= %s", (uid, target))
    total_sec = cur.fetchone()[0]
    
    cur.execute("SELECT COALESCE(SUM(calls_h),0), COALESCE(SUM(nsu_h),0), COUNT(*) FROM hourly_stats WHERE user_id=%s AND date >= %s", (uid, target))
    stats = cur.fetchone()
    
    conn.close()
    
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    
    bot.edit_message_text(f"📊 <b>Report: {user_name}</b>\n⏳ মোট কাজ: {h} ঘণ্টা {m} মিনিট\n📑 Hourly: {stats[2]} বার\n📞 Calls: {stats[0]} | 📉 NSU: {stats[1]}", call.message.chat.id, call.message.message_id)

# =======================================================
# ⏰ অটোমেশন ও ওয়ার্নিং সিস্টেম (Detailed Logic)
# =======================================================
def automation():
    best_alert = False
    greet = {"m": False, "a": False, "e": False}
    
    while True:
        try:
            now = bd_time()
            
            # সকাল ৯টায় বেস্ট পারফর্মার রিমাইন্ডার (শুধুমাত্র অ্যাডমিন গ্রুপে)
            if now.hour == 9 and now.minute == 0 and not best_alert:
                try:
                    bot.send_message(ADMIN_GROUP_ID, f"🔔 {ADMIN_MENTION} <b>গতকালকের Best Performer</b> ঘোষণার সময় হয়েছে।")
                    best_alert = True
                except Exception as e:
                    pass
                    
            if now.hour == 0: 
                best_alert = False
                greet = {"m": False, "a": False, "e": False}

            # শুভেচ্ছা বার্তা (সকলের জন্য - অ্যাডমিনসহ)
            if now.hour == 8 and now.minute == 0 and not greet["m"]: 
                send_to_all("☀️ <b>শুভ সকাল!</b>\nকাজে মন দিন এবং আজকের লক্ষ্য পূরণ করুন। 🚀")
                greet["m"] = True
                
            if now.hour == 14 and now.minute == 0 and not greet["a"]: 
                send_to_all("🌤️ <b>শুভ দুপুর!</b>\nসাফল্যের জন্য আপনার চেষ্টাই যথেষ্ট। এগিয়ে যান! 💪")
                greet["a"] = True
                
            if now.hour == 18 and now.minute == 0 and not greet["e"]: 
                send_to_all("🌆 <b>শুভ সন্ধ্যা!</b>\nপেশাদারিত্বের সাথে পরিশ্রম চালিয়ে যান। ✨")
                greet["e"] = True

            # ডাটাবেস চেক করে ওয়ার্নিং ও রিমাইন্ডার পাঠানো
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT a.user_id, a.status, a.last_break_time, a.start_time, a.last_report_time, u.name, u.username FROM attendance a JOIN users u ON a.user_id = u.user_id")
            rows = cur.fetchall()
            
            for u, s, lb, st, lr, name, username in rows:
                
                # অ্যাডমিন চেক (টেলিগ্রাম ইউজারনেম দিয়ে)
                is_u_admin = is_admin_user(username)
                
                # --- ওয়ার্নিং ও রিমাইন্ডার (অ্যাডমিনদের ছাড়া) ---
                if not is_u_admin:
                    
                    # ১. বিরতি ওয়ার্নিং (৫০ মিনিট ও ১ ঘণ্টা)
                    if s == 'break' and lb:
                        diff = (now - datetime.strptime(lb, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        
                        if 3000 <= diff <= 3060: # ৫০ মিনিট
                            try:
                                bot.send_message(u, "🔔 বিরতির ৫০ মিনিট পূর্ণ। কাজে ফেরার সময় হয়েছে। 😊")
                            except Exception as e:
                                pass
                                
                        if 3600 <= diff <= 3660: # ১ ঘণ্টা (অ্যাডমিন গ্রুপে)
                            try:
                                bot.send_message(ADMIN_GROUP_ID, f"⚠️ <b>Warning:</b> {name} ১ ঘণ্টার বেশি সময় ধরে বিরতিতে আছেন!")
                            except Exception as e:
                                pass
                    
                    # ২. ১ ঘণ্টা পূর্ণ হলে আওয়ারলি রিপোর্ট রিমাইন্ডার (পার্সোনাল DM)
                    if s == 'working' and st:
                        diff_start = (now - datetime.strptime(st, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        
                        if 3600 <= diff_start <= 3660: # ঠিক ১ ঘণ্টা পর
                            try:
                                bot.send_message(u, "📢 <b>রিমাইন্ডার:</b>\nআপনার Hourly Report submit দেওয়া সময় হয়েছে।")
                            except Exception as e:
                                pass
                            
                    # ৩. ১ ঘণ্টা ৩০ মিনিট ধরে রিপোর্ট না দিলে গ্রুপ ওয়ার্নিং
                    if s == 'working' and lr:
                        diff_report = (now - datetime.strptime(lr, "%Y-%m-%d %H:%M:%S")).total_seconds()
                        
                        if 5400 <= diff_report <= 5460: # ১ ঘণ্টা ৩০ মিনিট
                            try:
                                bot.send_message(ADMIN_GROUP_ID, f"⚠️ <b>Warning:</b> {name} গত ১ ঘণ্টা ৩০ মিনিট ধরে কোনো Hourly Report জমা দেননি!", message_thread_id=TOPIC_HOURLY)
                            except Exception as e:
                                pass
                            
                    # ৪. রাত ১০ টায় ডিউটি শেষ অ্যালার্ট (যাদের কাজ সকাল ১০টায় শুরু হয়েছিল)
                    if s == 'working' and st and now.hour == 22 and now.minute == 0:
                        start_time_obj = datetime.strptime(st, "%Y-%m-%d %H:%M:%S")
                        
                        if start_time_obj.hour == 10: 
                            try:
                                bot.send_message(u, "📢 সময় শেষ! শেষ রিপোর্ট দিয়ে ডিউটি শেষ করুন।")
                            except Exception as e:
                                pass
            
            conn.close()
            time.sleep(60)
            
        except Exception as e: 
            print("Automation Loop Error:", e)
            time.sleep(60)

threading.Thread(target=automation, daemon=True).start()

# =======================================================
# 🌐 রানার (Web Server Keep-Alive)
# =======================================================
app = Flask(__name__)

@app.route('/')
def home(): 
    return "🤖 Bot is Online with Expanded Formatting and Features!"

def run_bot():
    bot.remove_webhook()
    while True:
        try:
            bot.infinity_polling(timeout=20, skip_pending=True)
        except Exception as e:
            print("Polling Error:", e)
            time.sleep(5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
