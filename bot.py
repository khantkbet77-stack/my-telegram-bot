import datetime
import os
import threading
import time
import pytz
import telebot
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
API_TOKEN = "8683150922:AAFBcqOyG6YugrzfL6u3nRmu9zz9yJwqiDc"
bot = telebot.TeleBot(API_TOKEN, parse_mode="HTML")

ADMINS = ["alamin_041", "aminal041"]
BACKUP_GROUP_ID = -1003210815541
TOPIC_SUPPORT = 5
TOPIC_APPLY = 9

# Data Stores
users_db = {}
admin_temp = {}
temp_data = {}
roll_counter = 10000

# ==========================================
# 2. MULTI-LANGUAGE DICTIONARY (Fixed English/Bangla)
# ==========================================
lang_dict = {
    'bn': {
        'menu_chat': '💬 লাইভ সাপোর্ট',
        'menu_apply': '📝 সার্ভিস রিকোয়েস্ট',
        'menu_docs': '📁 ডকুমেন্টস',
        'menu_embassy': '🏛️ এম্বাসি প্রশ্নোত্তর',
        'menu_exam': '📅 এক্সাম শিডিউল',
        'menu_contact': '📞 আমাদের সম্পর্কে',
        'menu_status': '📊 স্ট্যাটাস চেক',
        'menu_admin': '⚙️ এডমিন প্যানেল',
        'not_approved': '⚠️ <b>অ্যাক্সেস ডিনাইড!</b>\nআপনার একাউন্টটি এখনও ভেরিফাই করা হয়নি।',
        'chat_close_btn': '❌ চ্যাট বন্ধ করুন'
    },
    'en': {
        'menu_chat': '💬 Live Support',
        'menu_apply': '📝 Service Request',
        'menu_docs': '📁 Documents',
        'menu_embassy': '🏛️ Embassy Q&A',
        'menu_exam': '📅 Exam Schedule',
        'menu_contact': '📞 About Us',
        'menu_status': '📊 Check Status',
        'menu_admin': '⚙️ Admin Panel',
        'not_approved': '⚠️ <b>Access Denied!</b>\nYour account is pending verification.',
        'chat_close_btn': '❌ End Chat'
    }
}

# ==========================================
# 3. UTILITIES & BACKGROUND REMINDER THREAD
# ==========================================
def show_typing(chat_id):
    try:
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(0.3)
    except:
        pass

def get_live_time(lang):
    bd_tz = pytz.timezone('Asia/Dhaka')
    ru_tz = pytz.timezone('Europe/Moscow')
    now_utc = datetime.datetime.now(pytz.utc)
    bd_time = now_utc.astimezone(bd_tz).strftime('%I:%M %p | %d %b %Y')
    ru_time = now_utc.astimezone(ru_tz).strftime('%I:%M %p | %d %b %Y')
    
    if lang == 'bn':
        return f"⏱ <b>লাইভ টাইম জোন</b>\n━━━━━━━━━━━━━━━━━━━━━━\n🇧🇩 <b>ঢাকা:</b> <code>{bd_time}</code>\n🇷🇺 <b>মস্কো:</b> <code>{ru_time}</code>\n━━━━━━━━━━━━━━━━━━━━━━\n"
    else:
        return f"⏱ <b>Live Timezone</b>\n━━━━━━━━━━━━━━━━━━━━━━\n🇧🇩 <b>Dhaka:</b> <code>{bd_time}</code>\n🇷🇺 <b>Moscow:</b> <code>{ru_time}</code>\n━━━━━━━━━━━━━━━━━━━━━━\n"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot Server is Live!')

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def is_admin(username):
    if not username:
        return False
    return username.lower() in [a.lower() for a in ADMINS]

# Background thread for 1 hour before exam auto-reminder
def exam_reminder_checker():
    while True:
        try:
            now = datetime.datetime.now()
            for chat_id, data in users_db.items():
                exam_dt = data.get('exam_dt')
                if exam_dt and not data.get('reminder_sent', False):
                    time_diff = exam_dt - now
                    # If remaining time is between 59 to 61 minutes
                    if 3540 <= time_diff.total_seconds() <= 3720:
                        sub = data.get('exam_sub', 'Exam')
                        dt = data.get('exam_date', '')
                        tm = data.get('exam_time', '')
                        bot.send_message(chat_id, f"⚠️ <b>সতর্কবার্তা (Reminder)!</b>\nআপনার আগামী ১ ঘণ্টার মধ্যে পরীক্ষা রয়েছে!\n📖 সাবজেক্ট: {sub}\n📅 তারিখ ও সময়: {dt} - {tm}")
                        users_db[chat_id]['reminder_sent'] = True
        except Exception as e:
            print(f"Reminder Error: {e}")
        time.sleep(60)

# ==========================================
# 4. BOT START & MAIN MENU
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    show_typing(chat_id)
    
    if chat_id not in users_db:
        users_db[chat_id] = {
            'lang': 'bn', 'is_approved': False, 'roll': None, 
            'exam_dt': None, 'exam_results': {}, 'status_msg': None, 'reminder_sent': False
        }
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(chat_id, "🌐 <b>Please select your preferred language:</b>\nআপনার পছন্দের ভাষা নির্বাচন করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['lang_bn', 'lang_en'])
def set_lang(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['lang'] = 'bn' if call.data == 'lang_bn' else 'en'
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    show_main_menu(chat_id)

def show_main_menu(chat_id):
    show_typing(chat_id)
    u_data = users_db.get(chat_id, {'lang': 'bn', 'is_approved': False})
    lang = u_data['lang']
    t_dict = lang_dict[lang]
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(t_dict['menu_chat'], t_dict['menu_apply'])
    
    if u_data.get('is_approved'):
        markup.add(t_dict['menu_docs'], t_dict['menu_embassy'])
        markup.add(t_dict['menu_exam'], t_dict['menu_status'])
        markup.add(t_dict['menu_contact'])
        
    try:
        if is_admin(bot.get_chat(chat_id).username):
            markup.add(t_dict['menu_admin'])
    except:
        pass

    header = get_live_time(lang)
    bot.send_message(chat_id, f"{header}\n✨ <b>মেইন মেনু</b> ✨", reply_markup=markup)

# ==========================================
# 5. FIXED BUTTONS: Embassy Q&A, Documents, Exam Schedule
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_embassy'], lang_dict['en']['menu_embassy']])
def embassy_qa_handler(message):
    chat_id = message.chat.id
    txt = (
        "🏛️ <b>এম্বাসি প্রশ্নোত্তর (Embassy Q&A)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "১. ফাইল প্রসেসিং কতদিন সময় নেয়?\n"
        "উত্তর: সাধারণত ২ থেকে ৩ সপ্তাহ সময় লাগে।\n\n"
        "২. ইন্টারভিউয়ের জন্য কী প্রস্তুতি নিতে হবে?\n"
        "উত্তর: বেসিক কমিউনিকেশন এবং ডকুমেন্ট ফাইল গুছিয়ে রাখতে হবে।"
    )
    bot.send_message(chat_id, txt)

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_docs'], lang_dict['en']['menu_docs']])
def documents_handler(message):
    chat_id = message.chat.id
    txt = (
        "📁 <b>প্রয়োজনীয় ডকুমেন্টস গাইডলাইন (Documents)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "• পাসপোর্ট (কমপক্ষে ৬ মাস মেয়াদ)\n"
        "• ছবি (সাদা ব্যাকগ্রাউন্ড)\n"
        "• একাডেমিক সার্টিফিকেট ও ট্রান্সক্রিপ্ট\n"
        "• ব্যাংক সলভেন্সি সার্টিফিকেট"
    )
    bot.send_message(chat_id, txt)

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_exam'], lang_dict['en']['menu_exam']])
def exam_schedule_user_handler(message):
    chat_id = message.chat.id
    u_data = users_db.get(chat_id, {})
    sub = u_data.get('exam_sub')
    dt = u_data.get('exam_date')
    tm = u_data.get('exam_time')
    
    if sub and dt and tm:
        txt = (
            "📅 <b>আপনার পরীক্ষার শিডিউল:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 সাবজেক্ট: <b>{sub}</b>\n"
            f"📅 তারিখ: <code>{dt}</code>\n"
            f"⏰ সময়: <code>{tm}</code>"
        )
    else:
        txt = "📅 <b>এক্সাম শিডিউল:</b>\nআপনার জন্য এখনো কোনো শিডিউল সেট করা হয়নি। এডমিন কর্তৃক সেট করার পর এখানে দেখতে পাবেন।"
    bot.send_message(chat_id, txt)

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_contact'], lang_dict['en']['menu_contact']])
def contact_handler(message):
    bot.send_message(message.chat.id, "📞 <b>যোগাযোগ:</b>\nযেকোনো প্রয়োজনে লাইভ চ্যাটে আমাদের সাথে যোগাযোগ করুন।")

# ==========================================
# 6. APPLY SERVICE
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_apply'], lang_dict['en']['menu_apply']])
def apply_service(message):
    chat_id = message.chat.id
    if users_db[chat_id].get('is_approved'):
        bot.send_message(chat_id, "✅ আপনি ইতিমধ্যেই একজন ভেরিফাইড ইউজার!")
        return
    temp_data[chat_id] = {}
    msg = bot.send_message(chat_id, "👤 <b>আপনার পূর্ণাঙ্গ নাম লিখুন:</b>")
    bot.register_next_step_handler(msg, step_wa)

def step_wa(message):
    chat_id = message.chat.id
    temp_data[chat_id]['name'] = message.text
    msg = bot.send_message(chat_id, "📱 <b>আপনার সচল WhatsApp নম্বরটি দিন:</b>")
    bot.register_next_step_handler(msg, step_cat)

def step_cat(message):
    chat_id = message.chat.id
    temp_data[chat_id]['wa'] = message.text
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("🎓 Scholarship Support", callback_data="cat_sch"),
           types.InlineKeyboardButton("🤖 Technical Support", callback_data="cat_bot"))
    bot.send_message(chat_id, "🎯 <b>সার্ভিস ক্যাটেগরি নির্বাচন করুন:</b>", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data in ['cat_sch', 'cat_bot'])
def finish_apply(call):
    global roll_counter
    chat_id = call.message.chat.id
    roll_counter += 1
    roll = roll_counter
    
    users_db[chat_id]['roll'] = roll
    users_db[chat_id]['name'] = temp_data[chat_id]['name']
    
    try:
        bot.edit_message_text(f"✅ <b>রিকুয়েষ্ট সাবমিট হয়েছে!</b>\n🔖 রোল: <code>{roll}</code>", chat_id, call.message.message_id)
    except:
        pass

    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"apprv_{chat_id}"),
           types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{chat_id}"))
    admin_txt = f"🚨 <b>NEW REQUEST</b>\n👤 Name: {users_db[chat_id]['name']}\n🔖 Roll: <code>{roll}</code>\n🔗 User: <code>{chat_id}</code>"
    bot.send_message(BACKUP_GROUP_ID, admin_txt, message_thread_id=TOPIC_APPLY, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('apprv_') or c.data.startswith('rej_'))
def handle_approval(call):
    action, uid = call.data.split('_')
    uid = int(uid)
    if action == 'apprv':
        users_db[uid]['is_approved'] = True
        try:
            bot.edit_message_text(call.message.text + "\n\n✅ <b>APPROVED</b>", call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(uid, "🎉 <b>অভিনন্দন!</b>\nআপনার একাউন্ট ভেরিফাই করা হয়েছে।")
        show_main_menu(uid)
    else:
        try:
            bot.edit_message_text(call.message.text + "\n\n❌ <b>REJECTED</b>", call.message.chat.id, call.message.message_id)
        except:
            pass

# ==========================================
# 7. LIVE CHAT SYSTEM
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_chat'], lang_dict['en']['menu_chat']])
def start_live_chat(message):
    chat_id = message.chat.id
    lang = users_db.get(chat_id, {}).get('lang', 'bn')
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add(lang_dict[lang]['chat_close_btn'])
    bot.send_message(chat_id, "🎧 <b>সাপোর্টে স্বাগতম!</b>\nমেসেজ দিন। চ্যাট শেষ করতে নিচের বাটনে ক্লিক করুন।", reply_markup=mk)
    users_db[chat_id]['in_chat'] = True

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['chat_close_btn'], lang_dict['en']['chat_close_btn']])
def user_close_chat(message):
    chat_id = message.chat.id
    roll = users_db.get(chat_id, {}).get('roll', 'N/A')
    
    bot.send_message(chat_id, "⏳ <b>চ্যাট বন্ধ করার অনুরোধ অ্যাডমিনের কাছে পাঠানো হয়েছে। অনুমোদনের জন্য অপেক্ষা করুন।</b>")
    
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("✅ OK (Close Chat)", callback_data=f"confirmclose_{chat_id}"))
    bot.send_message(BACKUP_GROUP_ID, f"🛑 <b>Chat Closure Request</b>\nUser Roll: <code>{roll}</code> wants to close.", message_thread_id=TOPIC_SUPPORT, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('confirmclose_'))
def admin_confirm_close(call):
    uid = int(call.data.split('_')[1])
    users_db[uid]['in_chat'] = False
    bot.send_message(uid, "✨ <b>চ্যাট সফলভাবে বন্ধ করা হয়েছে। ধন্যবাদ!</b>")
    try:
        bot.edit_message_text("✅ Chat closed securely.", call.message.chat.id, call.message.message_id)
    except:
        pass
    show_main_menu(uid)

@bot.message_handler(content_types=['text', 'photo', 'document'], func=lambda m: m.chat.type == 'private' and users_db.get(m.chat.id, {}).get('in_chat', False))
def forward_to_admin(message):
    chat_id = message.chat.id
    roll = users_db.get(chat_id, {}).get('roll', 'N/A')
    caption = f"💬 [Roll: <code>{roll}</code>]\n🆔 ID: <code>{chat_id}</code>"
    
    if message.content_type == 'text':
        bot.send_message(BACKUP_GROUP_ID, f"{caption}\n\n📝 {message.text}", message_thread_id=TOPIC_SUPPORT)
    elif message.content_type == 'photo':
        bot.send_photo(BACKUP_GROUP_ID, message.photo[-1].file_id, caption=caption, message_thread_id=TOPIC_SUPPORT)
    elif message.content_type == 'document':
        bot.send_document(BACKUP_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=TOPIC_SUPPORT)

@bot.message_handler(func=lambda m: m.chat.id == BACKUP_GROUP_ID and m.message_thread_id == TOPIC_SUPPORT and m.reply_to_message)
def admin_reply(message):
    import re
    reply_txt = message.reply_to_message.text or message.reply_to_message.caption
    if reply_txt:
        match = re.search(r'ID: <code>(\d+)</code>', reply_txt)
        if match:
            target_id = int(match.group(1))
            if message.content_type == 'text':
                bot.send_message(target_id, f"🎧 <b>Support:</b>\n{message.text}")

# ==========================================
# 8. USER STATUS SYSTEM
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_status'], lang_dict['en']['menu_status']])
def user_status_menu(message):
    msg = bot.send_message(message.chat.id, "আপনার রোল নাম্বারটি টাইপ করে পাঠান:")
    bot.register_next_step_handler(msg, process_user_status_roll)

def process_user_status_roll(message):
    roll = message.text.strip()
    target_uid = None
    for uid, data in users_db.items():
        if str(data.get('roll')) == roll:
            target_uid = uid
            break
            
    if target_uid:
        mk = types.InlineKeyboardMarkup(row_width=1)
        mk.add(
            types.InlineKeyboardButton("১. পরীক্ষার ফলাফল", callback_data=f"usrres_{target_uid}"),
            types.InlineKeyboardButton("২. সর্বশেষ আপডেট", callback_data=f"usrupd_{target_uid}")
        )
        bot.send_message(message.chat.id, f"✅ রোল <code>{roll}</code> পাওয়া গেছে। অপশন নির্বাচন করুন:", reply_markup=mk)
    else:
        bot.send_message(message.chat.id, "❌ এই রোল নাম্বারের কোনো ইউজার পাওয়া যায়নি।")

@bot.callback_query_handler(func=lambda c: c.data.startswith('usrres_') or c.data.startswith('usrupd_'))
def handle_user_status_view(call):
    action, uid = call.data.split('_')
    uid = int(uid)
    data = users_db.get(uid, {})
    
    if action == 'usrres':
        results = data.get('exam_results', {})
        if not results:
            txt = "ℹ️ এখনো কোনো পরীক্ষার ফলাফল যোগ করা হয়নি।"
        else:
            txt = "🎓 <b>আপনার পরীক্ষার ফলাফল:</b>\n━━━━━━━━━━━━━━\n"
            for sub, marks in results.items():
                txt += f"📖 <b>{sub}:</b> {marks} নম্বর\n"
        bot.send_message(call.message.chat.id, txt)
        
    elif action == 'usrupd':
        status = data.get('status_msg')
        if not status:
            bot.send_message(call.message.chat.id, "⏳ আপনার স্ট্যাটাস আপডেটের জন্য অ্যাডমিনকে রিকোয়েস্ট পাঠানো হয়েছে।")
            mk = types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton("সেট করুন", callback_data=f"admstat_set_{uid}"))
            bot.send_message(BACKUP_GROUP_ID, f"🔔 <b>Status Request:</b>\nRoll: <code>{data.get('roll')}</code> স্ট্যাটাস জানতে চাইছে, কিন্তু সেট করা নেই!", reply_markup=mk)
        else:
            bot.send_message(call.message.chat.id, f"🔄 <b>সর্বশেষ আপডেট:</b>\n\n( {status} )")
    try:
        bot.answer_callback_query(call.id)
    except:
        pass

# ==========================================
# 9. SUPER ADMIN PANEL & ALL USER NOTICE
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_admin'], lang_dict['en']['menu_admin']])
def admin_panel(message):
    if not is_admin(message.from_user.username):
        return
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("👥 User Details (Remove/Manage)", callback_data="adm_users"),
        types.InlineKeyboardButton("📅 Exam Schedule Setup", callback_data="adm_exam"),
        types.InlineKeyboardButton("📊 Status Update", callback_data="adm_status"),
        types.InlineKeyboardButton("📢 All User Notice (Image/Text)", callback_data="adm_notice")
    )
    bot.send_message(message.chat.id, "🛠️ <b>এডমিন প্যানেল</b>", reply_markup=mk)

# --- Admin: User Details & Remove ---
@bot.callback_query_handler(func=lambda c: c.data == 'adm_users')
def admin_manage_users(call):
    mk = types.InlineKeyboardMarkup(row_width=1)
    has_users = False
    for uid, data in users_db.items():
        if data.get('is_approved'):
            has_users = True
            mk.add(types.InlineKeyboardButton(f"👤 {data['name']} (Roll: {data['roll']})", callback_data=f"usrsel_{uid}"))
    
    if has_users:
        bot.send_message(call.message.chat.id, "ক্লিক করে ইউজার রিমুভ করুন:", reply_markup=mk)
    else:
        bot.answer_callback_query(call.id, "কোনো ইউজার নেই!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith('usrsel_'))
def admin_user_action(call):
    uid = call.data.split('_')[1]
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("🗑️ রিমুভ করুন (Revoke)", callback_data=f"rmv_{uid}"))
    try:
        bot.edit_message_text("এই ইউজারকে বাতিল করতে নিচের বাটনে ক্লিক করুন:", call.message.chat.id, call.message.message_id, reply_markup=mk)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith('rmv_'))
def execute_user_remove(call):
    uid = int(call.data.split('_')[1])
    if uid in users_db:
        users_db[uid]['is_approved'] = False
        try:
            bot.edit_message_text("✅ ইউজারকে সফলভাবে রিমুভ করা হয়েছে।", call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(uid, "⚠️ <b>আপনার এক্সেস বাতিল করা হয়েছে।</b>")

# --- Admin: Exam Schedule Setup (Step-by-step) ---
@bot.callback_query_handler(func=lambda c: c.data == 'adm_exam')
def admin_exam_select(call):
    mk = types.InlineKeyboardMarkup(row_width=1)
    for uid, data in users_db.items():
        if data.get('is_approved'):
            mk.add(types.InlineKeyboardButton(f"{data['name']} (Roll: {data['roll']})", callback_data=f"exmset_{uid}"))
    bot.send_message(call.message.chat.id, "কার শিডিউল সেট করবেন তা সিলেক্ট করুন:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('exmset_'))
def exam_step_subject(call):
    uid = int(call.data.split('_')[1])
    admin_temp[call.message.chat.id] = {'target_uid': uid}
    msg = bot.send_message(call.message.chat.id, "📖 <b>সাবজেক্টের নাম লিখুন:</b>")
    bot.register_next_step_handler(msg, exam_step_date)

def exam_step_date(message):
    admin_temp[message.chat.id]['subject'] = message.text
    msg = bot.send_message(message.chat.id, "📅 <b>তারিখ লিখুন (যেমন: 25-12-2026):</b>")
    bot.register_next_step_handler(msg, exam_step_time)

def exam_step_time(message):
    admin_temp[message.chat.id]['date'] = message.text
    msg = bot.send_message(message.chat.id, "⏰ <b>সময় লিখুন (যেমন: 10:00 AM):</b>")
    bot.register_next_step_handler(msg, exam_step_finalize)

def exam_step_finalize(message):
    chat_id = message.chat.id
    time_str = message.text
    temp = admin_temp.get(chat_id, {})
    uid = temp.get('target_uid')
    
    if uid and uid in users_db:
        try:
            date_str = temp['date']
            subject = temp['subject']
            exam_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %I:%M %p")
            
            users_db[uid].update({
                'exam_sub': subject, 
                'exam_date': date_str, 
                'exam_time': time_str, 
                'exam_dt': exam_dt,
                'reminder_sent': False
            })
            bot.send_message(chat_id, "✅ শিডিউল সফলভাবে সেট করা হয়েছে!")
            bot.send_message(uid, f"🔔 <b>New Exam Schedule!</b>\nSubject: {subject}\nDate: {date_str} at {time_str}")
        except Exception as e:
            bot.send_message(chat_id, f"❌ ফর্মেট বা তারিখ ভুল হয়েছে: {e}")

# --- Admin: Status Update ---
@bot.callback_query_handler(func=lambda c: c.data == 'adm_status' or c.data.startswith('admstat_set_'))
def admin_status_menu(call):
    pre_selected_uid = None
    if call.data.startswith('admstat_set_'):
        pre_selected_uid = int(call.data.split('_')[2])
    
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("১. Exam Result", callback_data="admst_res"),
        types.InlineKeyboardButton("২. Status", callback_data="admst_upd")
    )
    if pre_selected_uid:
        admin_temp[call.message.chat.id] = {'target_uid': pre_selected_uid}
        bot.send_message(call.message.chat.id, "এই ইউজারের কী আপডেট করবেন?", reply_markup=mk)
    else:
        bot.send_message(call.message.chat.id, "আপডেট অপশন নির্বাচন করুন:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data in ['admst_res', 'admst_upd'])
def admin_status_select_user(call):
    action = call.data
    if not admin_temp.get(call.message.chat.id, {}).get('target_uid'):
        mk = types.InlineKeyboardMarkup(row_width=1)
        for uid, data in users_db.items():
            if data.get('is_approved'):
                mk.add(types.InlineKeyboardButton(f"{data['name']} (Roll: {data['roll']})", callback_data=f"{action}_user_{uid}"))
        try:
            bot.edit_message_text("ব্যবহারকারী নির্বাচন করুন:", call.message.chat.id, call.message.message_id, reply_markup=mk)
        except:
            pass
    else:
        uid = admin_temp[call.message.chat.id]['target_uid']
        if action == 'admst_res':
             ask_result_sub(call.message, uid)
        else:
             show_status_options(call.message, uid)

@bot.callback_query_handler(func=lambda c: c.data.startswith('admst_res_user_'))
def handle_admst_res_user(call):
    uid = int(call.data.split('_')[3])
    ask_result_sub(call.message, uid)

def ask_result_sub(message, uid):
    admin_temp[message.chat.id] = {'target_uid': uid}
    msg = bot.send_message(message.chat.id, "📖 <b>সাবজেক্টের নাম লিখুন:</b>")
    bot.register_next_step_handler(msg, ask_result_marks)

def ask_result_marks(message):
    admin_temp[message.chat.id]['subject'] = message.text
    msg = bot.send_message(message.chat.id, "💯 <b>ফলাফল (নম্বর) লিখুন:</b>")
    bot.register_next_step_handler(msg, save_result)

def save_result(message):
    chat_id = message.chat.id
    marks = message.text
    temp = admin_temp.get(chat_id, {})
    uid = temp.get('target_uid')
    sub = temp.get('subject')
    
    if uid and uid in users_db:
        if 'exam_results' not in users_db[uid]:
            users_db[uid]['exam_results'] = {}
        users_db[uid]['exam_results'][sub] = marks
        bot.send_message(chat_id, "✅ ফলাফল সফলভাবে সেভ হয়েছে!")
        bot.send_message(uid, f"🎓 <b>নতুন পরীক্ষার ফলাফল প্রকাশ হয়েছে!</b>\n📖 সাবজেক্ট: {sub}\n💯 নম্বর: {marks}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('admst_upd_user_'))
def handle_admst_upd_user(call):
    uid = int(call.data.split('_')[3])
    show_status_options(call.message, uid)

def show_status_options(message, uid):
    admin_temp[message.chat.id] = {'target_uid': uid}
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("1. In work", callback_data="stupd_In work"),
        types.InlineKeyboardButton("2. Paused", callback_data="stupd_Paused"),
        types.InlineKeyboardButton("3. Activities are ongoing", callback_data="stupd_Activities are ongoing"),
        types.InlineKeyboardButton("4. There are no updates", callback_data="stupd_There are no updates"),
        types.InlineKeyboardButton("✍️ কাস্টম স্ট্যাটাস লিখুন", callback_data="stupd_custom")
    )
    bot.send_message(message.chat.id, "স্ট্যাটাস সিলেক্ট করুন অথবা কাস্টম লিখুন:", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('stupd_'))
def process_status_choice(call):
    status_val = call.data.split('_')[1]
    uid = admin_temp.get(call.message.chat.id, {}).get('target_uid')
    
    if not uid:
        return
        
    if status_val == 'custom':
        msg = bot.send_message(call.message.chat.id, "📝 <b>স্ট্যাটাসটি লিখে পাঠান:</b>")
        bot.register_next_step_handler(msg, save_custom_status, uid)
    else:
        users_db[uid]['status_msg'] = status_val
        try:
            bot.edit_message_text(f"✅ স্ট্যাটাস ({status_val}) সেট করা হয়েছে!", call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_message(uid, f"🔄 <b>আপনার স্ট্যাটাস আপডেট হয়েছে:</b>\n\n( {status_val} )")

def save_custom_status(message, uid):
    if uid in users_db:
        users_db[uid]['status_msg'] = message.text
        bot.send_message(message.chat.id, "✅ কাস্টম স্ট্যাটাস সেভ হয়েছে!")
        bot.send_message(uid, f"🔄 <b>আপনার স্ট্যাটাস আপডেট হয়েছে:</b>\n\n( {message.text} )")

# --- Admin: All User Notice (Congratulatory & General Notice with Image/Text) ---
@bot.callback_query_handler(func=lambda c: c.data == 'adm_notice')
def admin_notice_menu(call):
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("🥳 অভিনন্দন বার্তা (Congratulatory)", callback_data="notif_congrats"),
        types.InlineKeyboardButton("📢 সাধারণ নোটিশ বার্তা (General Notice)", callback_data="notif_general")
    )
    bot.send_message(call.message.chat.id, "কোন ধরনের নোটিশ পাঠাতে চান?", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data in ['notif_congrats', 'notif_general'])
def admin_notice_type_select(call):
    ntype = "अभिनন্দন বার্তা (Congratulatory)" if call.data == 'notif_congrats' else "সাধারণ নোটিশ (General Notice)"
    admin_temp[call.message.chat.id] = {'notice_type': ntype}
    msg = bot.send_message(call.message.chat.id, f"📝 <b>{ntype} এর মেসেজ ও ছবি (যদি থাকে) দিন:</b>\n(প্রথমে ছবি পাঠাতে পারেন অথবা শুধু টেক্সট পাঠাতে পারেন)")
    bot.register_next_step_handler(msg, broadcast_notice_step)

def broadcast_notice_step(message):
    chat_id = message.chat.id
    ntype = admin_temp.get(chat_id, {}).get('notice_type', 'Notice')
    
    success_count = 0
    for uid, data in users_db.items():
        if data.get('is_approved'):
            try:
                if message.photo:
                    caption = f"🚨 <b>{ntype}</b>\n\n{message.caption or ''}"
                    bot.send_photo(uid, message.photo[-1].file_id, caption=caption)
                else:
                    text_content = f"🚨 <b>{ntype}</b>\n\n{message.text}"
                    bot.send_message(uid, text_content)
                success_count += 1
            except:
                pass
                
    bot.send_message(chat_id, f"✅ নোটিশ সফলভাবে পাঠানো হয়েছে! মোট প্রেরিত ইউজার: {success_count}")

# ==========================================
# 10. RUN BOT & THREADING
# ==========================================
if __name__ == "__main__":
    t1 = threading.Thread(target=run_web_server)
    t1.daemon = True
    t1.start()
    
    t2 = threading.Thread(target=exam_reminder_checker)
    t2.daemon = True
    t2.start()
    
    print("🚀 Bot Server and Reminder Thread Started Successfully...")
    bot.infinity_polling()
