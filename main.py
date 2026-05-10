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
ADMIN_GROUP_ID = -1003790774851 
ALLOWED_ADMINS = ['bdhasan09', 'alexbd96', 'aminal041']

TOPIC_HOURLY = 2
TOPIC_RECHARGE = 3
TOPIC_PAYMENT = 4
TOPIC_ATTENDANCE = 5
TOPIC_LEAVE = 6
# ===============================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
db_lock = threading.Lock()

def is_admin(user):
    if not user or not user.username: return False
    return user.username.lower() in ALLOWED_ADMINS

def clean_text(text):
    if not text: return "N/A"
    return text.replace("<", "").replace(">", "").replace("&", "and")

def setup_db():
    with db_lock:
        conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS attendance (user_id INTEGER PRIMARY KEY, status TEXT, start_time TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS work_hours (user_id INTEGER, month_year TEXT, total_seconds INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS message_map (admin_msg_id INTEGER PRIMARY KEY, user_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS hourly_stats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, time TEXT, calls_h INTEGER, nsu_h INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS reports_log (user_id INTEGER, date TEXT, time TEXT, log TEXT)")
        try: cursor.execute("ALTER TABLE attendance ADD COLUMN last_report_time TEXT")
        except: pass
        try: cursor.execute("ALTER TABLE work_hours ADD COLUMN date TEXT")
        except: pass
        conn.commit()
        conn.close()

setup_db()

def main_menu(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন")
    markup.add("⏱️ Daily Attendance", "📱 Recharges")
    markup.add("🩺 SL-OFF-issue")
    if is_admin(user): markup.add("👑 Admin Panel")
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
    except: return "Unknown User"

def is_cmd(message):
    btns = ["/start", "/menu", "📊 Hourly Report", "💳 ডিপোজিট/উত্তোলন", "⏱️ Daily Attendance", "📱 Recharges", "🩺 SL-OFF-issue", "👑 Admin Panel"]
    if message.text in btns:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        bot.process_new_messages([message])
        return True
    return False

@bot.message_handler(commands=['start'])
def start(message):
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
    except: bot.send_message(message.chat.id, "❌ সমস্যা হয়েছে। আবার /start দিন।")

@bot.message_handler(commands=['menu'])
def show_menu(message):
    bot.send_message(message.chat.id, "👇 <b>আপনার মেনু:</b>", reply_markup=main_menu(message.from_user))

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
        if res: bot.send_message(res[0], f"📩 <b>অ্যাডমিন রিপ্লাই:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.text)}")
    except: pass

@bot.message_handler(func=lambda m: m.text == "📊 Hourly Report")
def hourly(message):
    fmt = "Name: \nTotal Call (D): \nTotal NSU (D): \nTotal Call (H): \nTotal NSU (H): "
    txt = f"📑 <b>নতুন আওয়ারলি রিপোর্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 ফরম্যাটটি কপি করুন এবং <b>স্ক্রিনশটসহ</b> সাবমিট করুন:\n\n<code>{fmt}</code>"
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_hourly)

def save_hourly(message):
    if is_cmd(message): return
    if not message.photo: return bot.send_message(message.chat.id, "❌ ছবি/স্ক্রিনশট ছাড়া সাবমিট হবে না।", reply_markup=main_menu(message.from_user))
    name = get_user_name(message.chat.id)
    caption_txt = clean_text(message.caption)
    calls_h, nsu_h = 0, 0
    try:
        c_match = re.search(r"Total Call \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        n_match = re.search(r"Total NSU \(H\)[^\d]*(\d+)", caption_txt, re.IGNORECASE)
        if c_match: calls_h = int(c_match.group(1))
        if n_match: nsu_h = int(n_match.group(1))
    except: pass
    time_now, date_now = datetime.now().strftime('%I:%M %p'), datetime.now().strftime("%Y-%m-%d")
    report = f"📊 <b>HOURLY REPORT</b>\n👤 <b>User:</b> {name}\n⏰ <b>Time:</b> {time_now}\n━━━━━━━━━━━━━━━━━━\n📝 <b>Details:</b>\n{caption_txt}"
    try:
        sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_HOURLY)
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            cursor.execute("UPDATE attendance SET last_report_time = ? WHERE user_id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message.chat.id))
            cursor.execute("INSERT INTO hourly_stats (user_id, date, time, calls_h, nsu_h) VALUES (?, ?, ?, ?, ?)", (message.chat.id, date_now, time_now, calls_h, nsu_h))
            cursor.execute("INSERT INTO reports_log (user_id, date, time, log) VALUES (?, ?, ?, ?)", (message.chat.id, date_now, time_now, caption_txt))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ রিপোর্ট জমা হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

@bot.message_handler(func=lambda m: m.text == "💳 ডিপোজিট/উত্তোলন")
def dep_with_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("📥 ডিপোজিট", callback_data="req_dep"), types.InlineKeyboardButton("📤 উত্তোলন", callback_data="req_with"))
    bot.send_message(message.chat.id, "💳 <b>রিকুয়েস্ট ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['req_dep', 'req_with'])
def handle_dep_with(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    if call.data == "req_dep":
        txt = "📥 <b>ডিপোজিট রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 <b>স্ক্রিনশটসহ</b> ক্যাপশনে পূরণ করুন:\n\n<code>ইউজার নাম: \nমোবাইল নাম্বার: \nট্রানজেকশন আইডি: </code>"
        msg = bot.send_message(call.message.chat.id, txt)
        bot.register_next_step_handler(msg, lambda m: save_transaction(m, "DEPOSIT"))
    else:
        txt = "📤 <b>উত্তোলন রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 ফরম্যাটটি কপি করে পূরণ করুন:\n\n<code>ইউজার নাম: \nমোবাইল নাম্বার: \nলেনদেন আইডি: \nঅ্যামাউন্ট: </code>"
        msg = bot.send_message(call.message.chat.id, txt)
        bot.register_next_step_handler(msg, lambda m: save_transaction(m, "WITHDRAWAL"))

def save_transaction(message, req_type):
    if is_cmd(message): return
    if req_type == "DEPOSIT" and not message.photo: return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া রিকোয়েস্ট বাতিল।", reply_markup=main_menu(message.from_user))
    name = get_user_name(message.chat.id)
    cap = clean_text(message.caption if message.caption else message.text)
    report = f"💰 <b>{req_type} REQUEST</b>\n👤 <b>User:</b> {name}\n📝 <b>Details:</b>\n{cap}"
    try:
        if message.photo: sent = bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=report, message_thread_id=TOPIC_PAYMENT)
        else: sent = bot.send_message(ADMIN_GROUP_ID, report, message_thread_id=TOPIC_PAYMENT)
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT INTO message_map (admin_msg_id, user_id) VALUES (?, ?)", (sent.message_id, message.chat.id))
            conn.commit()
            conn.close()
        bot.send_message(message.chat.id, "✅ রিকুয়েষ্ট এডমিনের কাছে পাঠানো হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

@bot.message_handler(func=lambda m: m.text == "⏱️ Daily Attendance")
def attend_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🟢 ডিউটি শুরু", callback_data="sw"), types.InlineKeyboardButton("⏸️ বিরতি", callback_data="bw"), types.InlineKeyboardButton("🔴 ডিউটি শেষ", callback_data="pw"))
    bot.send_message(message.chat.id, "⏱️ <b>এটেনডেন্স প্যানেল</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ['sw', 'bw', 'pw'])
def attend_call(call):
    try: bot.answer_callback_query(call.id, "প্রসেস হচ্ছে...")
    except: pass
    uid, name, now = call.message.chat.id, get_user_name(call.message.chat.id), datetime.now()
    date_str, time_str, disp_time = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime('%I:%M %p')
    try:
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO attendance (user_id, status) VALUES (?, 'stopped')", (uid,))
            cursor.execute("SELECT status, start_time FROM attendance WHERE user_id=?", (uid,))
            row = cursor.fetchone()
            current_status, start_str = row[0] if row else 'stopped', row[1] if row else None

            if call.data == 'sw':
                if current_status == 'working': bot.send_message(uid, "⚠️ আপনি অ্যাক্টিভ আছেন!")
                else:
                    msg_text = "🟢 <b>Duty Resumed</b>" if current_status == 'break' else "🟢 <b>Duty Started</b>"
                    cursor.execute("UPDATE attendance SET status='working', start_time=?, last_report_time=? WHERE user_id=?", (time_str, time_str, uid))
                    try: bot.send_message(ADMIN_GROUP_ID, f"{msg_text}\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>ডিউটি শুরু হয়েছে!</b>", uid, call.message.message_id, parse_mode="HTML")

            elif call.data == 'bw':
                if current_status == 'break': bot.send_message(uid, "⚠️ আপনি বিরতিতেই আছেন!")
                elif current_status == 'stopped': bot.send_message(uid, "⚠️ আপনি কাজে ঢোকেননি!")
                else:
                    try: st = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    except: st = now
                    sec = max(int((now - st).total_seconds()), 0)
                    cursor.execute("SELECT 1 FROM work_hours WHERE user_id=? AND date=?", (uid, date_str))
                    if not cursor.fetchone(): cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (?, ?, 0)", (uid, date_str))
                    cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + ? WHERE user_id = ? AND date = ?", (sec, uid, date_str))
                    cursor.execute("UPDATE attendance SET status='break' WHERE user_id=?", (uid,))
                    try: bot.send_message(ADMIN_GROUP_ID, f"⏸️ <b>Break Started</b>\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>বিরতি শুরু হয়েছে!</b>", uid, call.message.message_id, parse_mode="HTML")

            elif call.data == 'pw':
                if current_status == 'stopped': bot.send_message(uid, "⚠️ ডিউটি আগেই শেষ!")
                else:
                    if current_status == 'working':
                        try: st = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                        except: st = now
                        sec = max(int((now - st).total_seconds()), 0)
                        cursor.execute("SELECT 1 FROM work_hours WHERE user_id=? AND date=?", (uid, date_str))
                        if not cursor.fetchone(): cursor.execute("INSERT INTO work_hours (user_id, date, total_seconds) VALUES (?, ?, 0)", (uid, date_str))
                        cursor.execute("UPDATE work_hours SET total_seconds = total_seconds + ? WHERE user_id = ? AND date = ?", (sec, uid, date_str))
                    cursor.execute("UPDATE attendance SET status='stopped' WHERE user_id=?", (uid,))
                    try: bot.send_message(ADMIN_GROUP_ID, f"🔴 <b>Duty Ended</b>\n👤 {name}\n⏰ {disp_time}", message_thread_id=TOPIC_ATTENDANCE)
                    except: pass
                    bot.edit_message_text("✅ <b>ডিউটি শেষ হয়েছে।</b>", uid, call.message.message_id, parse_mode="HTML")
            conn.commit()
            conn.close()
    except: bot.send_message(uid, "❌ সমস্যা হয়েছে।")

@bot.message_handler(func=lambda m: m.text == "📱 Recharges")
def recharge_app(message):
    txt = "📱 <b>রিচার্জ রিকোয়েস্ট</b>\n━━━━━━━━━━━━━━━━━━\n📢 <b>স্ক্রিনশটসহ</b> ক্যাপশন দিন:\n\n<code>তারিখ: \nমাস: \nবছর: \nঅ্যামাউন্ট: </code>"
    msg = bot.send_message(message.chat.id, txt)
    bot.register_next_step_handler(msg, save_recharge)

def save_recharge(message):
    if is_cmd(message): return
    if not message.photo: return bot.send_message(message.chat.id, "❌ স্ক্রিনশট ছাড়া হবে না।", reply_markup=main_menu(message.from_user))
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
        bot.send_message(message.chat.id, "✅ পাঠানো হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

@bot.message_handler(func=lambda m: m.text == "🩺 SL-OFF-issue")
def leave_menu(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🤒 অসুস্থ ছুটি", callback_data="lv_sick"), types.InlineKeyboardButton("🚨 ইমারজেন্সি ছুটি", callback_data="lv_emg"), types.InlineKeyboardButton("⚠️ সমস্যা", callback_data="lv_issue"))
    bot.send_message(message.chat.id, "🩺 <b>ধরন সিলেক্ট করুন:</b>", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('lv_'))
def handle_leave(call):
    try: bot.answer_callback_query(call.id)
    except: pass
    title = "অসুস্থ ছুটি" if call.data == "lv_sick" else ("ইমারজেন্সি ছুটি" if call.data == "lv_emg" else "সমস্যা")
    txt = f"📝 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━\nকপি করে পূরণ করুন:\n\n<code>তারিখ: \nবিস্তারিত: \nকত দিন: </code>"
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
        bot.send_message(message.chat.id, "✅ রিপোর্ট এডমিন গ্রুপে পাঠানো হয়েছে।")
    except: bot.send_message(message.chat.id, "❌ সার্ভার এরর।")

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel")
def admin_panel_menu(message):
    if not is_admin(message.from_user): return bot.send_message(message.chat.id, "⛔ <b>ডিনাইড!</b>")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📋 রিপোর্ট চেক", callback_data="admin_check"), types.InlineKeyboardButton("🏆 Best Performer", callback_data="admin_best"), types.InlineKeyboardButton("📢 প্রমোশন মেসেজ", callback_data="admin_promo"))
    bot.send_message(message.chat.id, "👑 <b>অ্যাডমিন প্যানেল:</b>", reply_markup=kb)

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
        kb = types.InlineKeyboardMarkup()
        for u in users: kb.add(types.InlineKeyboardButton(u[1], callback_data=f"rpt_{u[0]}"))
        bot.send_message(call.message.chat.id, "📊 <b>কার রিপোর্ট?</b>", reply_markup=kb)
        
    elif call.data == "admin_best":
        today, display_date = datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%d-%m-%Y")
        with db_lock:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute("SELECT u.name, SUM(h.nsu_h), SUM(h.calls_h) FROM hourly_stats h JOIN users u ON h.user_id = u.user_id WHERE h.date=? GROUP BY h.user_id ORDER BY SUM(h.nsu_h) DESC, SUM(h.calls_h) DESC LIMIT 1", (today,))
            best = cursor.fetchone()
            cursor.execute("SELECT user_id FROM users")
            all_users = cursor.fetchall()
            conn.close()
        if best and best[0]:
            txt = f"🏆 <b>Daily Best Performer</b> 🏆\n\n📅 Date: [{display_date}]\n👤 Name: {best[0]}\n📈 Result: NSU – {best[1]} | Call – {best[2]}\n\nCongratulations! 🚀"
            try: bot.send_message(ADMIN_GROUP_ID, txt)
            except: pass
            for u in all_users:
                try: bot.send_message(u[0], txt)
                except: pass
            bot.send_message(call.message.chat.id, "✅ পাঠানো হয়েছে।")
            
    elif call.data == "admin_promo":
        msg = bot.send_message(call.message.chat.id, "📢 <b>প্রমোশন মেসেজ লিখে সেন্ড করুন:</b>")
        bot.register_next_step_handler(msg, send_promotion)

def send_promotion(message):
    if is_cmd(message): return
    broadcast_msg = f"📢 <b>অ্যাডমিন নোটিশ:</b>\n━━━━━━━━━━━━━━━━━━\n{clean_text(message.text)}"
    with db_lock:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
    for u in users:
        try: bot.send_message(u[0], broadcast_msg)
        except: pass
    bot.send_message(message.chat.id, "✅ মেসেজ পাঠানো হয়েছে।")

@bot.callback_query_handler(func=lambda c: c.data.startswith('rpt_'))
def select_report_range(call):
    if not is_admin(call.from_user): return
    uid = call.data.split('_')[1]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("২৪ ঘন্টা", callback_data=f"dr_{uid}_1"), types.InlineKeyboardButton("৭ দিন", callback_data=f"dr_{uid}_7"), types.InlineKeyboardButton("১৫ দিন", callback_data=f"dr_{uid}_15"), types.InlineKeyboardButton("৩০ দিন", callback_data=f"dr_{uid}_30"))
    bot.edit_message_text("⏳ <b>দিন সিলেক্ট করুন:</b>", call.message.chat.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('dr_'))
def show_final_report(call):
    if not is_admin(call.from_user): return
    parts = call.data.split('_')
    uid, days = int(parts[1]), int(parts[2])
    target_date = (datetime.now() - timedelta(days=days-1)).strftime("%Y-%m-%d")
    with db_lock:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id=?", (uid,))
        name = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(total_seconds) FROM work_hours WHERE user_id=? AND date >= ?", (uid, target_date))
        total_sec = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(calls_h), SUM(nsu_h), COUNT(*) FROM hourly_stats WHERE user_id=? AND date >= ?", (uid, target_date))
        stat = cursor.fetchone()
        t_calls, t_nsu, t_reports = stat[0] or 0, stat[1] or 0, stat[2] or 0
        cursor.execute("SELECT date, time, log FROM reports_log WHERE user_id=? AND date >= ?", (uid, target_date))
        logs = cursor.fetchall()
        conn.close()
    h, m = total_sec // 3600, (total_sec % 3600) // 60
    txt = f"📊 <b>Report: {name} ({days} Days)</b>\n━━━━━━━━━━━━━━━━━━\n⏳ <b>কাজ:</b> {h} ঘণ্টা {m} মিনিট\n📑 <b>Hourly:</b> {t_reports} বার\n📞 <b>Calls:</b> {t_calls} | 📉 <b>NSU:</b> {t_nsu}\n━━━━━━━━━━━━━━━━━━\n"
    if logs:
        txt += "📝 <b>রিপোর্টসমূহ:</b>\n"
        for l in logs[-5:]: txt += f"[{l[0]} | {l[1]}] {l[2][:40]}...\n"
    try: bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode="HTML")
    except: pass

def automation():
    while True:
        try:
            now = datetime.now()
            if now.minute % 15 == 0:
                with db_lock:
                    conn = sqlite3.connect('bot_database.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT user_id, last_report_time FROM attendance WHERE status='working'")
                    for u, lr in cursor.fetchall():
                        if lr and (now - datetime.strptime(lr, "%Y-%m-%d %H:%M:%S")).total_seconds() >= 3600:
                            try: bot.send_message(u, "📢 <b>Hourly report টাইম হয়েছে!</b>")
                            except: pass
                            cursor.execute("UPDATE attendance SET last_report_time = ? WHERE user_id = ?", (now.strftime("%Y-%m-%d %H:%M:%S"), u))
                            conn.commit()
                    conn.close()
            time.sleep(60)
        except: time.sleep(60)

threading.Thread(target=automation, daemon=True).start()

# ================= 🌐 Flask Web Server & 🚀 Run Bot =================
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is Online & Running 24/7 on Render!"

def run_bot():
    print("🚀 Telegram Bot is starting in background...")
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            print("Bot crashed, restarting in 5 seconds... Error:", e)
            time.sleep(5)

# বটকে ব্যাকগ্রাউন্ডে চালু করা
threading.Thread(target=run_bot, daemon=True).start()

# মেইন থ্রেডে ওয়েব সার্ভার চালু করা (যাতে Render কখনো বন্ধ না করে)
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port)
