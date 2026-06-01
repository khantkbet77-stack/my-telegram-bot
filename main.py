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

# 🔒 বটের সিকিউরিটি পাসওয়ার্ড (বাইরের মানুষ আটকাতে এটি নতুন যোগ করা হলো)
BOT_PASSWORD = "Tkbet77ST"

# অ্যাডমিন লিস্ট (এদেরকে কোনো ওয়ার্নিং বা রিমাইন্ডার দেওয়া হবে না)
ALLOWED_ADMINS = ['aminal041', 'bdhasan09', 'alexbd96']
ADMIN_MENTION = "@AlexBD96"

# টপিক আইডি সমূহ
TOPIC_PAYMENT = 3       
TOPIC_ATTENDANCE = 10   
TOPIC_RECHARGE = 13     
TOPIC_HOURLY = 88       
TOPIC_LEAVE = 405       

DB_URL = "postgresql://postgres:Tkbet77Alamin@db.jbyoziiykcymahmeyxsm.supabase.co:6543/postgres?sslmode=disable"
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
        
        # অন্যান্য প্রয়োজনীয় টেবিল
        cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id BIGINT PRIMARY KEY, status TEXT, start_time TEXT, last_report_time TEXT, last_break_time TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS work_hours (user_id BIGINT, date TEXT, total_seconds INTEGER DEFAULT 0, UNIQUE(user_id, date))")
        cursor.execute("CREATE TABLE IF NOT EXISTS message_map (admin_msg_id BIGINT PRIMARY KEY, user_id BIGINT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS hourly_stats (id SERIAL PRIMARY KEY, user_id BIGINT, date TEXT, time TEXT, calls_h INTEGER, nsu_h INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports_log (user_id BIGINT, date TEXT, time TEXT, log TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS recharges (id SERIAL PRIMARY KEY, user_id BIGINT, date TEXT, time TEXT, amount REAL, details TEXT)")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Setup Error:", e)

# 🩺 ছুটির ডাটা সেভ করার জন্য নতুন টেবিল তৈরি (এটি setup_db এর বাইরে আলাদা থাকবে)
def init_leave_db():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_leaves (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                name VARCHAR(100),
                leave_type VARCHAR(50),
                apply_date DATE,
                details TEXT,
                extra_seconds BIGINT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'Pending',
                group_msg_id BIGINT DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print("Leave DB Init Error:", e)

# 🚀 দুটি ফাংশনকেই একে একে রান করানো হলো
setup_db()
init_leave_db()

# =======================================================
# 🎛️ মেনু ও রেজিস্ট্রেশন
# =======================================================
def main_menu(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন")
    markup.add("⏱️ Daily Attendance", "📱 Recharges")
    markup.add("🩺 SL-OFF-issue") # এখান থেকে "🆘 হেল্প ও সাপোর্ট" মুছে ফেলা হয়েছে
    
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
        # নতুন ইউজার হলে আগে পাসওয়ার্ড চাইবে
        msg = bot.send_message(message.chat.id, "🔒 <b>বটটি সিকিউর করা হয়েছে!</b>\n\nসিস্টেম ব্যবহার করতে দয়া করে টিমের <b>পাসওয়ার্ড (Secret Code)</b> টি লিখে সেন্ড করুন:")
        bot.register_next_step_handler(msg, check_password)

# 🔒 পাসওয়ার্ড চেক করার নতুন ফাংশন
def check_password(message):
    if is_cmd(message): return
    
    if message.text.strip() == BOT_PASSWORD:
        msg = bot.send_message(message.chat.id, "✅ <b>পাসওয়ার্ড সঠিক!</b>\n\nসিস্টেম ব্যবহারের জন্য এবার আপনার <b>পুরো নাম</b> লিখে সেন্ড করুন:")
        bot.register_next_step_handler(msg, register)
    else:
        bot.send_message(message.chat.id, "❌ <b>পাসওয়ার্ড ভুল!</b>\nসঠিক পাসওয়ার্ড ছাড়া আপনি এই বট ব্যবহার করতে পারবেন না। আবার চেষ্টা করতে /start লিখুন।")

def register(message):
    if is_cmd(message):
        return
        
    clean_name = clean_text(message.text)
    user_id = message.chat.id
    username = message.from_user.username.lower() if message.from_user.username else ""
    
    try:
        conn = get_conn()
        cursor = conn.cursor()
        
        # এখানে কোনো ভুল আছে কি না তা চেক করতে print ব্যবহার করছি
        sql = "INSERT INTO users (user_id, name, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET name = %s, username = %s"
        cursor.execute(sql, (user_id, clean_name, username, clean_name, username))
        
        conn.commit()
        cursor.close() # cursor close করা জরুরি
        conn.close()
        
        bot.send_message(user_id, f"🎊 রেজিস্ট্রেশন সফল! স্বাগতম <b>{clean_name}</b>।", reply_markup=main_menu(message.from_user))
        
    except Exception as e:
        # এবার বট আপনাকে পরিষ্কার বলবে কেন হচ্ছে না
        bot.send_message(user_id, f"❌ ডাটাবেস এরর: {e}")
        print(f"Error details: {e}")

# =======================================================
# ✅ অ্যাকশন বাটন লজিক (Approve / Reject / Work - ৩ নম্বর পার্ট)
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
    
    # যে টপিকে ক্লিক করা হয়েছে, সেটার আইডি বের করা
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
            # 🟢 [নতুন লজিক] ডাটাবেসে স্ট্যাটাস Approved করে দেওয়া
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("UPDATE user_leaves SET status = 'Approved' WHERE group_msg_id = %s", (msg.message_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                print("DB Approve Update Error:", e)

            bot.send_message(uid, "✅ <b>আপনার রিকোয়েস্টটি অ্যাডমিন দ্বারা Approve করা হয়েছে!</b>")
            final_text = "\n\n✅ <b>Status:</b> Approved by " + admin_name
            work_status_str = "\n\n⚙️ <b>Status:</b> <i>Working on it...</i>"
            
            if msg.content_type == 'photo':
                clean_caption = (msg.caption or "").replace(work_status_str, "")
                bot.edit_message_caption(caption=clean_caption + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
            else:
                clean_text_content = (msg.text or "").replace(work_status_str, "")
                bot.edit_message_text(text=clean_text_content + final_text, chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None, parse_mode="HTML")
                
        elif action == 'rej':
            # রিজেক্ট করার কারণ চাওয়ার লজিক - এখন নির্দিষ্ট টপিকেই মেসেজ যাবে!
            prompt_msg = bot.send_message(
                call.message.chat.id, 
                f"⚠️ <b>{admin_name}</b>, দয়া করে রিকোয়েস্টটি রিজেক্ট করার কারণ লিখে সেন্ড করুন (না দিতে চাইলে 'Skip' লিখুন):",
                message_thread_id=thread_id
            )
            bot.register_next_step_handler(prompt_msg, process_rejection_reason, uid, msg, admin_name, prompt_msg.message_id)
            
    except Exception as e:
        bot.answer_callback_query(call.id, "অ্যাকশন আপডেট করতে সমস্যা হয়েছে!")

def process_rejection_reason(message, uid, original_msg, admin_name, prompt_msg_id):
    if is_cmd(message): 
        return
        
    reason = clean_text(message.text)
    user_msg = "❌ <b>আপনার রিকোয়েস্টটি অ্যাডমিন দ্বারা Reject করা হয়েছে।</b>"
    
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
        
    # 🔴 [নতুন লজিক] অ্যাডমিন Reject করার পর ডাটাবেসে স্ট্যাটাস Rejected করে দেওয়া
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE user_leaves SET status = 'Rejected' WHERE group_msg_id = %s", (original_msg.message_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Reject Update Error:", e)

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
        
    # গ্রুপ পরিষ্কার রাখতে অ্যাডমিনের রিপ্লাই এবং বটের প্রশ্ন ডিলিট করে দেওয়া
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
    
    # ক্যাপশন থেকে এমাউন্ট (Amount) বের করার লজিক
    amt = 0.0
    try:
        match = re.search(r"(?:এমাউন্টও?|এমাউন্ট|Amount)[\s:]*([\d\,\.]+)", cap, re.IGNORECASE)
        if match:
            amt = float(match.group(1).replace(',', ''))
    except Exception as e:
        pass
    
    now = bd_time()
    d_str = now.strftime("%Y-%m-%d")
    t_str = now.strftime("%I:%M %p")
    
    try:
        bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=f"📱 <b>RECHARGE</b>\n👤 {name}\n📝 {cap}", reply_markup=act_kb, message_thread_id=TOPIC_RECHARGE)
        
        # রিচার্জ ডাটাবেসে সেভ করা
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO recharges (user_id, date, time, amount, details) VALUES (%s, %s, %s, %s, %s)", (message.chat.id, d_str, t_str, amt, cap))
        conn.commit()
        conn.close()
        
        bot.send_message(message.chat.id, "✅ পাঠানো হয়েছে।")
    except Exception as e:
        pass

# =======================================================
# ৫. 🩺 SL-OFF-issue (বানান, স্পেস ও None ফিক্স)
# =======================================================
@bot.message_handler(func=lambda m: m.text is not None and ("SL-OFF-issue" in m.text or "SL-OFF-issu" in m.text))
def leave_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🤒 অসুস্থ ছুটি", callback_data="lv_sick"), 
        types.InlineKeyboardButton("⏳ অতিরিক্ত বিরতি সময়", callback_data="lv_extra"), 
        types.InlineKeyboardButton("🆘 ইমারজেন্সি কাজ", callback_data="lv_emg"),
        types.InlineKeyboardButton("🌗 হাফ ডে (Half Day)", callback_data="lv_half")
    )
    bot.send_message(message.chat.id, "🩺 ধরন সিলেক্ট করুন:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('lv_'))
def handle_leave(call):
    bot.answer_callback_query(call.id) # বাটন ক্লিকের ঘড়ি ঘুরানি বন্ধ করার জন্য
    
    # হাফ ডে-তে ক্লিক করলে আলাদা প্রসেস শুরু হবে
    if call.data == "lv_half":
        msg = bot.send_message(call.message.chat.id, "📅 <b>হাফ ডে (Half Day) রিকোয়েস্ট:</b>\n\nযে তারিখের জন্য হাফ ডে চাচ্ছেন, সেটি লিখে充ন্ড করুন\n(যেমন: 25-05-2026):")
        bot.register_next_step_handler(msg, process_half_date)
        return
        
    # অন্যান্য ছুটির প্রসেস
    if call.data == "lv_sick":
        fmt = "তারিখ: \nবিস্তারিত: \nদিন: "
        mode = "SICK LEAVE"
    elif call.data == "lv_extra":
        fmt = "তারিখ (DD-MM-YYYY): \nমোট অতিরিক্ত সময় (মিনিট হিসেবে, যেমন- ৩০ বা ৯০): \nকারণ: "
        mode = "EXTRA BREAK"
    elif call.data == "lv_emg":
        fmt = "তারিখ: \nকারণ: \nডকুমেন্টস: "
        mode = "EMERGENCY WORK"
        
    txt = f"📝 {mode}\n\n<code>{fmt}</code>"
    if mode == "EMERGENCY WORK":
        txt += "\n(স্ক্রিনশট বাধ্যতামূলক)"
        
    msg = bot.send_message(call.message.chat.id, txt, parse_mode="HTML")
    bot.register_next_step_handler(msg, lambda ms: save_leave(ms, mode))

def save_leave(message, mode):
    if is_cmd(message): return
    
    uid = message.chat.id
    name = get_user_name(uid)
    act_kb = get_action_buttons(uid)
    now_dt = bd_time().date()
    
    # ইমারজেন্সি কাজের জন্য স্ক্রিনশট বা ফটো বাধ্যতামূলক চেক
    if mode == "EMERGENCY WORK" and not message.photo:
        bot.send_message(uid, "❌ ইমারজেন্সি কাজের আবেদনের জন্য স্ক্রিনশট (Photo) পাঠানো বাধ্যতামূলক। দয়া করে আবার চেষ্টা করুন।")
        return
        
    cap = clean_text(message.caption if message.photo else message.text)
    report = f"🩺 <b>{mode}</b>\n👤 {name}\n📢 {ADMIN_MENTION}\n📝 {cap}"
    
    # অতিরিক্ত বিরতির মিনিট ক্যালকুলেট করার লজিক
    extra_sec = 0
    if mode == "EXTRA BREAK":
        try:
            for line in cap.split('\n'):
                if "মোট অতিরিক্ত সময়" in line or "সময়" in line:
                    mins = int(''.join(filter(str.isdigit, line)))
                    extra_sec = mins * 60
                    break
        except:
            extra_sec = 0

    try:
        # প্রথমে গ্রুপে মেসেজ পাঠানো (ফটো অথবা টেক্সট অনুযায়ী)
        if message.photo:
            sent_msg = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE, parse_mode="HTML")
        else:
            sent_msg = bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE, parse_mode="HTML")
        
        # ডাটাবেসে 'Pending' স্ট্যাটাস এবং গ্রুপ মেসেজ আইডি সহ সেভ করা
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO user_leaves (user_id, name, leave_type, apply_date, details, extra_seconds, status, group_msg_id) VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)", 
                    (uid, name, mode, now_dt, cap, extra_sec, sent_msg.message_id))
        conn.commit()
        conn.close()
        
        bot.send_message(uid, "✅ আপনার আবেদনটি অ্যাডমিন প্যানেলে পাঠানো হয়েছে। অ্যাডমিন Approve করলে এটি কাউন্ট হবে।")
    except Exception as e:
        print("Save Leave Error:", e)
        bot.send_message(uid, "❌ রিকোয়েস্টটি ডাটাবেসে সেভ করতে সমস্যা হয়েছে।")

# -------------------------------------------------------
# 🌗 হাফ ডে (Half Day) এর লজিক ও বাটন
# -------------------------------------------------------
def process_half_date(message):
    if is_cmd(message): return
    date_text = clean_text(message.text)[:20]
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("☀️ দিন (সকাল ১০:০০ - ১৬:০০)", callback_data=f"hds_day_{date_text}"),
        types.InlineKeyboardButton("🌙 রাত (১৬:০০ - ২২:০০)", callback_data=f"hds_ngt_{date_text}")
    )
    bot.send_message(message.chat.id, f"📅 তারিখ: <b>{date_text}</b>\n\nএবার আপনার শিফট সিলেক্ট করুন:", reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith('hds_'))
def process_half_shift(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split('_', 2)
    shift_code = parts[1] 
    date_text = parts[2]
    
    shift_name = "দিন (১০:০০ - ১৬:০০)" if shift_code == 'day' else "রাত (১৬:০০ - ২২:০০)"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Yes (রাজি)", callback_data=f"hdc_y_{shift_code}_{date_text}"),
        types.InlineKeyboardButton("❌ No", callback_data="hdc_n")
    )
    
    txt = f"⚠️ <b>হাফ ডে শর্তাবলি:</b>\n\nআপনি <b>{date_text}</b> তারিখে <b>{shift_name}</b> শিফটে হাফ ডে ডিউটি করতে চাচ্ছেন।\n\n📌 <i>নোট: এই হাফ ডে ডিউটিতে আপনি বিরতি পাবেন মাত্র ৩০ মিনিট।</i>\n\nআপনি কি রাজি?"
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data.startswith('hdc_'))
def process_half_confirm(call):
    # ১. যদি ইউজার সরাসরি No বাটনে ক্লিক করে
    if call.data == "hdc_n":
        bot.answer_callback_query(call.id)
        return bot.edit_message_text("❌ আপনার হাফ ডে রিকোয়েস্টটি বাতিল করা হয়েছে।", call.message.chat.id, call.message.message_id)
        
    # ২. যদি ইউজার Yes বাটনে ক্লিক করে (ডাটা প্রসেস করা হচ্ছে)
    try:
        bot.answer_callback_query(call.id)
        parts = call.data.split('_', 3)
        shift_code = parts[2]  # day অথবা ngt
        date_text = parts[3]   # ইউজারের দেওয়া তারিখ
        
        shift_name = "দিন (১০:০০ - ১৬:০০)" if shift_code == 'day' else "রাত (১৬:০০ - ২২:০০)"
        name = get_user_name(call.message.chat.id)
        act_kb = get_action_buttons(call.message.chat.id)
        
        report = f"🌗 <b>HALF DAY REQUEST</b>\n👤 User: {name}\n📢 <b>Admin:</b> {ADMIN_MENTION}\n📅 তারিখ: <b>{date_text}</b>\n⏱️ শিফট: <b>{shift_name}</b>\n📌 নোট: ইউজার ৩০ মিনিট বিরতির শর্তে রাজি হয়েছেন।"
        
        # গ্রুপে মেসেজ পাঠানো
        sent_msg = bot.send_message(ADMIN_GROUP_ID, report, reply_markup=act_kb, message_thread_id=TOPIC_LEAVE, parse_mode="HTML")
        
        # ডাটাবেসে Pending হিসেবে হাফ ডে সেভ করা
        conn = get_conn()
        cur = conn.cursor()
        now_dt = bd_time().date()
        cur.execute("INSERT INTO user_leaves (user_id, name, leave_type, apply_date, details, status, group_msg_id) VALUES (%s, %s, %s, %s, %s, 'Pending', %s)", 
                    (call.message.chat.id, name, "HALF DAY", now_dt, f"তারিখ: {date_text}, শিফট: {shift_name}", sent_msg.message_id))
        conn.commit()
        conn.close()
        
        # ইউজারকে বটের ইনবক্সে কনফার্মেশন দেখানো
        bot.edit_message_text("✅ আপনার হাফ ডে রিকোয়েস্ট পাঠানো হয়েছে। অ্যাডমিন Approve করলে এটি কাউন্ট হবে।", call.message.chat.id, call.message.message_id)
        
    except Exception as e:
        print("Save Half Day Error:", e)
        bot.answer_callback_query(call.id, "❌ প্রসেস করতে সমস্যা হয়েছে! আবার চেষ্টা করুন।")
        
# =======================================================
# 👑 অ্যাডমিন প্যানেল ও রিচার্জ/ছুটি রিপোর্ট (১০০% জ্যাম-ফ্রি চূড়ান্ত সংস্করণ)
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
        types.InlineKeyboardButton("📢 আপডেট নোটিশ পাঠান", callback_data="adm_upd_not"),
        types.InlineKeyboardButton("📱 রিচার্জ রিপোর্ট", callback_data="rech_main_menu"),
        types.InlineKeyboardButton("🩺 ছুটির রিপোর্ট চেক", callback_data="adm_leave_check")
    )
    bot.send_message(message.chat.id, "👑 অ্যাডমিন প্যানেল:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_"))
def handle_adm_callback(call):
    if not is_admin_obj(call.from_user):
        return
        
    try: bot.answer_callback_query(call.id)
    except: pass
        
    if call.data == "adm_upd_not":
        msg = bot.send_message(call.message.chat.id, "📢 <b>আপডেট নোটিশটি লিখুন:</b>")
        bot.register_next_step_handler(msg, broadcast_promo)
        
    elif call.data == "adm_mention":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users WHERE name IS NOT NULL")
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
        cur.execute("SELECT user_id, name FROM users WHERE name IS NOT NULL")
        users_list = cur.fetchall()
        conn.close()
        
        kb = types.InlineKeyboardMarkup()
        for x in users_list:
            kb.add(types.InlineKeyboardButton(f"❌ Remove: {x[1]}", callback_data=f"del_{x[0]}"))
            
        bot.edit_message_text("👤 ইউজার রিমুভ:", call.message.chat.id, call.message.message_id, reply_markup=kb)
        
    elif call.data == "adm_check":
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("👤 একজন একজন করে", callback_data="chk_mode_single"),
            types.InlineKeyboardButton("👥 সবার একসাথে (আজ)", callback_data="chk_mode_all_today"),
            types.InlineKeyboardButton("📅 কাস্টম তারিখ (সবাই একসাথে)", callback_data="chk_mode_all_custom")
        )
        bot.edit_message_text("📊 <b>রিপোর্ট দেখার ধরন বেছে নিন:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

    # 🟢 কলব্যাক ডাটা 'lvrpt_' দিয়ে আলাদা করা হলো যেন উপরের বা নিচের কোনো হ্যান্ডলারের সাথে ক্ল্যাশ না করে
    elif call.data == "adm_leave_check":
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("👤 একজন একজন করে (ছুটি)", callback_data="lvrpt_single"),
            types.InlineKeyboardButton("👥 সবার একসাথে (চলতি মাস)", callback_data="lvrpt_all_month"),
            types.InlineKeyboardButton("📅 কাস্টম তারিখ (ছুটির রিপোর্ট)", callback_data="lvrpt_custom")
        )
        bot.edit_message_text("🩺 <b>ছুটি ও হাফ ডে রিপোর্ট দেখার ধরন বেছে নিন:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mnt_"))
def mnt_step_2(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    uid = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "💬 মেনশন মেসেজ লিখুন (ছবিসহ হতে পারে):")
    bot.register_next_step_handler(msg, lambda m: send_mnt(m, uid))

def send_mnt(message, uid):
    if is_cmd(message): return
    txt = f"📩 <b>অ্যাডমিন আপনাকে মেনশন করেছে:</b>\n\n{clean_text(message.caption if message.photo else message.text)}"
    try:
        if message.photo:
            bot.send_photo(uid, message.photo[-1].file_id, caption=txt)
        else:
            bot.send_message(uid, txt)
        bot.send_message(message.chat.id, "✅ মেনশন পাঠানো হয়েছে।")
    except: pass

def broadcast_best(message):
    if is_cmd(message): return
    txt = f"🌟 <b>সেরা পারফর্মার!</b> 🌟\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.caption if message.photo else message.text)}"
    send_to_all(txt, message.photo)

def broadcast_promo(message):
    if is_cmd(message): return
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
            if photo: bot.send_photo(u[0], photo[-1].file_id, caption=txt)
            else: bot.send_message(u[0], txt)
        except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def del_u(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    uid = call.data.split("_")[1]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))
    conn.commit()
    conn.close()
    bot.edit_message_text("✅ ইউজার রিমুভড।", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rpt_"))
def rpt_range(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    uid = call.data.split("_")[1]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("২৪ ঘণ্টা", callback_data=f"dr_{uid}_1"), 
        types.InlineKeyboardButton("৭ দিন", callback_data=f"dr_{uid}_7"), 
        types.InlineKeyboardButton("১৫ দিন", callback_data=f"dr_{uid}_15"), 
        types.InlineKeyboardButton("৩০ দিন", callback_data=f"dr_{uid}_30")
    )
    bot.edit_message_text("⏳ সময় নির্বাচন করুন:", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dr_"))
def rpt_final(call):
    try: bot.answer_callback_query(call.id)
    except: pass
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
# 📱 রিচার্জ রিপোর্ট সেকশন (Recharge Report Logic)
# =======================================================
@bot.callback_query_handler(func=lambda c: c.data == "rech_main_menu")
def adm_rech_menu(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("👥 সবার রিপোর্ট (চলতি মাস)", callback_data="rech_all"),
        types.InlineKeyboardButton("👤 নির্দিষ্ট ব্যক্তির (চলতি মাস)", callback_data="rech_users"),
        types.InlineKeyboardButton("📅 কাস্টম তারিখ (Custom Date)", callback_data="rech_custom")
    )
    bot.edit_message_text("📱 <b>রিচার্জ রিপোর্ট প্যানেল:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "rech_all")
def rech_all_report(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    now = bd_time()
    start_date = now.replace(day=1).strftime("%Y-%m-%d")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT u.name, SUM(r.amount), COUNT(r.id) FROM recharges r JOIN users u ON r.user_id = u.user_id WHERE r.date >= %s GROUP BY u.name", (start_date,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return bot.send_message(call.message.chat.id, " চলিষ্ণু মাসে কোনো রিচার্জ ডাটা নেই!")
        
    txt = f"📊 <b>সবার রিচার্জ রিপোর্ট (চলতি মাস)</b>\n📅 {start_date} থেকে আজ পর্যন্ত\n━━━━━━━━━━━━━━━━━━\n"
    total_amt = 0
    for name, amt, cnt in rows:
        txt += f"👤 {name}: <b>{amt} ৳</b> ({cnt} বার)\n"
        total_amt += amt
    txt += f"━━━━━━━━━━━━━━━━━━\n💰 <b>সর্বমোট: {total_amt} ৳</b>"
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "rech_users")
def rech_users_list(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT u.user_id, u.name FROM recharges r JOIN users u ON r.user_id = u.user_id")
    users_list = cursor.fetchall()
    conn.close()
    
    if not users_list:
        return bot.send_message(call.message.chat.id, "❌ কোনো ডাটা নেই!")
        
    kb = types.InlineKeyboardMarkup()
    for uid, name in users_list:
        kb.add(types.InlineKeyboardButton(name, callback_data=f"rech_indv_{uid}"))
    bot.edit_message_text("👤 কার রিপোর্ট দেখবেন?", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rech_indv_"))
def rech_indv_report(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    uid = int(call.data.split('_')[2])
    now = bd_time()
    start_date = now.replace(day=1).strftime("%Y-%m-%d")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE user_id=%s", (uid,))
    name = cursor.fetchone()[0]
    cursor.execute("SELECT date, time, amount FROM recharges WHERE user_id=%s AND date >= %s ORDER BY date ASC", (uid, start_date))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return bot.send_message(call.message.chat.id, "❌ চলতি মাসে ডাটা নেই!")
        
    txt = f"📊 <b>রিচার্জ বিস্তারিত: {name}</b>\n📅 চলতি মাস\n━━━━━━━━━━━━━━━━━━\n"
    total = 0
    for d, t, a in rows:
        txt += f"▪️ {d} | {t} ➔ <b>{a} ৳</b>\n"
        total += a
    txt += f"━━━━━━━━━━━━━━━━━━\n💰 <b>মোট: {total} ৳</b>"
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "rech_custom")
def rech_custom_prompt(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    msg = bot.send_message(
        call.message.chat.id, 
        "📅 <b>তারিখ অনুযায়ী রিপোর্ট:</b>\n\nদয়া করে শুরুর তারিখ এবং শেষের তারিখ লিখে সেন্ড করুন।\n\n👉 <b>ফরম্যাট:</b> দিন-跨াস-বছর দিন-মাস-বছর\n📝 <b>উদাহরণ:</b> 01-05-2026 15-05-2026"
    )
    bot.register_next_step_handler(msg, process_custom_date_report)

def process_custom_date_report(message):
    if is_cmd(message): return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ ফরম্যাট ভুল হয়েছে। (যেমন: 01-05-2026 15-05-2026)।")
            return
            
        d1_obj = datetime.strptime(parts[0], "%d-%m-%Y")
        d2_obj = datetime.strptime(parts[1], "%d-%m-%Y")
        start_db = d1_obj.strftime("%Y-%m-%d")
        end_db = d2_obj.strftime("%Y-%m-%d")
        
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT u.name, SUM(r.amount), COUNT(r.id) FROM recharges r JOIN users u ON r.user_id = u.user_id WHERE r.date >= %s AND r.date <= %s GROUP BY u.name", (start_db, end_db))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            bot.send_message(message.chat.id, f"📅 <b>{parts[0]}</b> থেকে <b>{parts[1]}</b> পর্যন্ত কোনো রিচার্জ ডাটা নেই!")
            return
            
        txt = f"📊 <b>কাস্টম রিচার্জ রিপোর্ট</b>\n📅 {parts[0]} থেকে {parts[1]}\n━━━━━━━━━━━━━━━━━━\n"
        total_amt = 0
        for name, amt, cnt in rows:
            txt += f"👤 {name}: <b>{amt} ৳</b> ({cnt} বার)\n"
            total_amt += amt
            
        txt += f"━━━━━━━━━━━━━━━━━━\n💰 <b>সর্বমোট: {total_amt} ৳</b>"
        bot.send_message(message.chat.id, txt)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ তারিখের ফরম্যাট সঠিক নয়। (DD-MM-YYYY)")
        
# =======================================================
# 📋 পুরোনো সাধারণ রিপোর্ট হ্যান্ডলার লিংক সমূহ
# =======================================================
@bot.callback_query_handler(func=lambda c: c.data == "chk_mode_single")
def legacy_single_list(call):
    try:
        bot.answer_callback_query(call.id)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users")
        users_list = cur.fetchall()
        conn.close()
        kb = types.InlineKeyboardMarkup()
        for x in users_list:
            kb.add(types.InlineKeyboardButton(x[1], callback_data=f"rpt_{x[0]}"))
        bot.edit_message_text("👤 কার রিপোর্ট দেখতে চান?", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "chk_mode_all_today")
def legacy_all_today(call):
    try:
        bot.answer_callback_query(call.id)
        now = bd_time()
        d_str = now.strftime("%Y-%m-%d")
        disp_date = now.strftime("%d %b, %Y")
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.name, COALESCE(w.total_seconds, 0),
                   (SELECT COUNT(*) FROM hourly_stats h WHERE h.user_id = u.user_id AND h.date = %s),
                   (SELECT COALESCE(SUM(calls_h), 0) FROM hourly_stats h WHERE h.user_id = u.user_id AND h.date = %s),
                   (SELECT COALESCE(SUM(nsu_h), 0) FROM hourly_stats h WHERE h.user_id = u.user_id AND h.date = %s)
            FROM users u LEFT JOIN work_hours w ON u.user_id = w.user_id AND w.date = %s
            WHERE w.total_seconds > 0 OR EXISTS (SELECT 1 FROM hourly_stats h WHERE h.user_id = u.user_id AND h.date = %s)
        """, (d_str, d_str, d_str, d_str, d_str))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            bot.edit_message_text("আজকে এখনো কোনো কাজের ডাটা নেই!", call.message.chat.id, call.message.message_id)
            return
        txt = f"📊 <b>সবার আজকের রিপোর্ট</b>\n📅 তারিখ: {disp_date}\n━━━━━━━━━━━━━━━━━━\n"
        for name, sec, h_count, calls, nsu in rows:
            h = sec // 3600
            m = (sec % 3600) // 60
            txt += f"👤 <b>{name}</b>\n⏳ কাজ: {h} ঘণ্টা {m} মিনিট | 📑 রিপোর্ট: {h_count}টি\n📞 Call: {calls} | 📉 NSU: {nsu}\n\n"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "chk_mode_all_custom")
def legacy_all_custom(call):
    try:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📅 <b>সবার কাস্টম তারিখের রিপোর্ট:</b>\n\nশুরুর তারিখ এবং শেষের তারিখ লিখে সেন্ড করুন।\n(যেমন: 01-05-2026 15-05-2026)")
        bot.register_next_step_handler(msg, process_all_users_custom_report)
    except: pass

# =======================================================
# 🩺 ৪. নতুন ছুটির রিপোর্ট হ্যান্ডলিং লজিক (১০০% ফিক্সড সংস্করণ)
# =======================================================

# ১. একজন একজন করে ছুটি দেখার জন্য ইউজার লিস্ট প্রসেস
@bot.callback_query_handler(func=lambda c: c.data == "lvrpt_single")
def lv_rpt_single_list(call):
    try:
        bot.answer_callback_query(call.id)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name FROM users WHERE name IS NOT NULL")
        users_list = cur.fetchall()
        conn.close()
        
        if not users_list:
            return bot.edit_message_text("❌ সিস্টেমে কোনো রেজিস্টার্ড ইউজার পাওয়া যায়নি!", call.message.chat.id, call.message.message_id)
            
        kb = types.InlineKeyboardMarkup(row_width=2)
        for x in users_list:
            if x[1]:
                # 🔒 ক্ল্যাশ বা জ্যাম এড়াতে callback_data 'rpt_' থেকে বদলে 'lvshw_' করা হলো
                kb.add(types.InlineKeyboardButton(str(x[1]), callback_data=f"lvshw_{x[0]}"))
            
        bot.edit_message_text("👤 কার ছুটির রিপোর্ট দেখতে চান?", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception as e:
        print("User List Error:", e)

# একক ইউজারের ছুটির মেইন রিপোর্ট দেখানোর ফাংশন (লক জ্যাম মুক্ত)
@bot.callback_query_handler(func=lambda c: c.data.startswith('lvshw_'))
def lv_rpt_single_show(call):
    try:
        bot.answer_callback_query(call.id)
        uid = int(call.data.split('_')[1])
        now = bd_time()
        start_month_str = now.replace(day=1).strftime("%Y-%m-%d")
        
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT leave_type, COUNT(*), COALESCE(SUM(extra_seconds), 0) 
            FROM user_leaves 
            WHERE user_id = %s AND apply_date >= %s AND status = 'Approved'
            GROUP BY leave_type
        """, (uid, start_month_str))
        rows = cur.fetchall()
        
        cur.execute("SELECT name FROM users WHERE user_id = %s", (uid,))
        u_row = cur.fetchone()
        uname = u_row[0] if u_row else "Unknown User"
        conn.close()
        
        txt = f"📑 <b>ছুটির রিপোর্ট: {uname}</b>\n📅 চলতি মাস: {now.strftime('%B %Y')}\n⚠️ <i>(Approved ছুটির হিসাব)</i>\n━━━━━━━━━━━━━━━━━━\n"
        
        sick, half, emg, extra_cnt, extra_sec = 0, 0, 0, 0, 0
        if rows:
            for ltype, count, ex_sec in rows:
                if ltype == "SICK LEAVE": sick = count
                elif ltype == "HALF DAY": half = count
                elif ltype == "EMERGENCY WORK": emg = count
                elif ltype == "EXTRA BREAK": 
                    extra_cnt = count
                    extra_sec = ex_sec
                    
        ex_h = extra_sec // 3600
        ex_m = (extra_sec % 3600) // 60
        
        txt += f"🤒 অসুস্থ ছুটি: {sick} বার\n"
        txt += f"🌗 হাফ ডে (Half Day): {half} বার\n"
        txt += f"🆘 ইমারজেন্সি কাজ: {emg} বার\n"
        txt += f"⏳ অতিরিক্ত বিরতি: {extra_cnt} বার (মোট: {ex_h} ঘণ্টা {ex_m} মিনিট)\n"
        
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)
    except Exception as e:
        print("Show Single Leave Error:", e)

# ২. সবার একসাথে চলতি মাসের ছুটির সামারি (নিখুঁত JOIN টেবিল লজিক)
@bot.callback_query_handler(func=lambda c: c.data == "lvrpt_all_month")
def lv_rpt_all_month_show(call):
    try:
        bot.answer_callback_query(call.id)
        now = bd_time()
        start_month_str = now.replace(day=1).strftime("%Y-%m-%d")
        
        conn = get_conn()
        cur = conn.cursor()
        # 👥 সবার ডাটা সঠিকভাবে টানতে users টেবিলের সাথে JOIN কোয়েরি করা হলো
        cur.execute("""
            SELECT u.name,
                   COUNT(CASE WHEN l.leave_type='SICK LEAVE' THEN 1 END) as sick,
                   COUNT(CASE WHEN l.leave_type='HALF DAY' THEN 1 END) as half,
                   COUNT(CASE WHEN l.leave_type='EMERGENCY WORK' THEN 1 END) as emg,
                   COUNT(CASE WHEN l.leave_type='EXTRA BREAK' THEN 1 END) as extra_cnt,
                   COALESCE(SUM(CASE WHEN l.leave_type='EXTRA BREAK' THEN l.extra_seconds ELSE 0 END), 0) as extra_sec
            FROM users u
            JOIN user_leaves l ON u.user_id = l.user_id
            WHERE l.apply_date >= CAST(%s AS DATE) AND l.status = 'Approved'
            GROUP BY u.name
        """, (start_month_str,))
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            return bot.edit_message_text("📊 <b>এই মাসে এখনও কোনো Approved ছুটির ডাটা নেই!</b>\nইউজার ছুটি সাবমিট করার পর অ্যাডমিন গ্রুপ থেকে Approve করলে এখানে শো করবে।", call.message.chat.id, call.message.message_id)
            
        txt = f"📊 <b>সবার ছুটির সামারি ({now.strftime('%B %Y')})</b>\n⚠️ <i>(Approved ছুটির হিসাব)</i>\n━━━━━━━━━━━━━━━━━━\n"
        for name, sick, half, emg, ex_cnt, ex_sec in rows:
            ex_h = ex_sec // 3600
            ex_m = (ex_sec % 3600) // 60
            txt += f"👤 <b>{name}</b>\n🤒 Sick: {sick} | 🌗 Half: {half} | 🆘 Emg: {emg}\n⏳ Extra: {ex_cnt} বার ({ex_h} ঘণ্টা {ex_m} মিনিট)\n\n"
            
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)
    except Exception as e:
        print("Bulk Report Error:", e)

# ৩. কাস্টম তারিখ অনুযায়ী ছুটির রিপোর্ট প্রম্পট
@bot.callback_query_handler(func=lambda c: c.data == "lvrpt_custom")
def lv_rpt_custom_prompt(call):
    try:
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id, 
            "📅 <b>কাস্টম ছুটির রিপোর্ট:</b>\n\nশুরুর ও শেষের তারিখ স্পেস দিয়ে লিখুন।\n\n👉 <b>ফরম্যাট:</b> দিন-মাস-বছর দিন-মাস-বছর\n📝 <b>উদাহরণ:</b> 01-05-2026 21-05-2026"
        )
        bot.register_next_step_handler(msg, process_custom_leave_report)
    except Exception as e:
        print("Custom Prompt Error:", e)

# কাস্টম ছুটির রিপোর্ট প্রসেস ফাংশন (ক্র্যাশ ফিক্সড)
def process_custom_leave_report(message):
    if is_cmd(message): return
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ ফরম্যাট ভুল। (যেমন: 01-05-2026 20-05-2026)")
            return
            
        d1_str = datetime.strptime(parts[0], "%d-%m-%Y").strftime("%Y-%m-%d")
        d2_str = datetime.strptime(parts[1], "%d-%m-%Y").strftime("%Y-%m-%d")
        
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT name, leave_type, apply_date, extra_seconds 
            FROM user_leaves 
            WHERE apply_date::text >= %s 
              AND apply_date::text <= %s 
              AND status = 'Approved'
            ORDER BY apply_date ASC
        """, (d1_str, d2_str))
        rows = cur.fetchall()
        conn.close()
        
        if not rows:
            bot.send_message(message.chat.id, f"📅 <b>{parts[0]}</b> থেকে <b>{parts[1]}</b> এর মধ্যে কোনো Approved ছুটির ডাটা নেই।")
            return
            
        txt = f"📊 <b>কাস্টম ছুটির রিপোর্ট ({parts[0]} থেকে {parts[1]})</b>\n━━━━━━━━━━━━━━━━━━\n"
        for name, ltype, ldate, ex_sec in rows:
            # ১. ডেট ফরম্যাট ক্র্যাশ ফিক্স (যেকোনো ফরম্যাট সাপোর্ট করবে)
            try:
                dt_str = ldate.strftime("%d-%m-%Y")
            except:
                dt_str = str(ldate)
                
            # ২. NULL বা None ডাটা ক্র্যাশ ফিক্স (None থাকলে ০ ধরে নেবে)
            ex_sec_val = ex_sec if ex_sec is not None else 0
            
            if ltype == "EXTRA BREAK":
                ex_m = ex_sec_val // 60
                txt += f"• <b>{name}</b> — {dt_str} [⏳ Extra Break: {ex_m} মিনিট]\n"
            else:
                txt += f"• <b>{name}</b> — {dt_str} [{ltype}]\n"
                
        bot.send_message(message.chat.id, txt)
    except Exception as e:
        print("Custom Leave Process Error:", e)
        bot.send_message(message.chat.id, "❌ তারিখ প্রসেস করতে সমস্যা হয়েছে অথবা ফরম্যাট ভুল। (DD-MM-YYYY)")
        
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
