import datetime
import os
import threading
import time
import pytz
import telebot
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# 1. VIP CONFIGURATION & SETUP
# ==========================================
API_TOKEN = "8683150922:AAFBcqOyG6YugrzfL6u3nRmu9zz9yJwqiDc"
bot = telebot.TeleBot(API_TOKEN, parse_mode="Markdown")

ADMINS = ["alamin_041", "aminal041"]
BACKUP_GROUP_ID = -1003210815541
TOPIC_SUPPORT = 5
TOPIC_APPLY = 9

# Database simulation (In-memory)
users_db = {}
temp_data = {}
roll_counter = 10000

# ==========================================
# 2. MULTI-LANGUAGE VIP DICTIONARY
# ==========================================
lang_dict = {
    'bn': {
        'menu_chat': '💬 লাইভ সাপোর্ট',
        'menu_apply': '📝 সার্ভিস রিকোয়েস্ট',
        'menu_docs': '📁 প্রয়োজনীয় ডকুমেন্টস',
        'menu_embassy': '🏛️ এম্বাসি প্রশ্নোত্তর',
        'menu_exam': '📅 এক্সাম শিডিউল',
        'menu_contact': '📞 আমাদের সম্পর্কে',
        'menu_admin': '⚙️ এডমিন প্যানেল',
        'not_approved': '⚠️ *অ্যাক্সেস ডিনাইড!*\nআপনার একাউন্টটি এখনও ভেরিফাই করা হয়নি। অনুগ্রহ করে অপেক্ষা করুন।',
        'ask_name': '👤 *আপনার পূর্ণাঙ্গ নাম লিখুন:*',
        'ask_wa': '📱 *আপনার সচল WhatsApp নম্বরটি দিন:*',
        'cat_select': '🎯 *সার্ভিস ক্যাটেগরি নির্বাচন করুন:*',
        'req_sent': '✅ *রিকুয়েষ্ট সফলভাবে সাবমিট হয়েছে!*\n\n🔖 আপনার ট্র্যাকিং রোল: `{roll}`\n\n_আমাদের টিম শীঘ্রই আপনার সাথে যোগাযোগ করবে।_',
        'chat_init': '🎧 *ভিআইপি সাপোর্টে স্বাগতম!*\n\nআমাদের একজন সাপোর্ট এজেন্ট শীঘ্রই যুক্ত হবেন। আপনার সমস্যাটি বিস্তারিত লিখে বা ছবি/ফাইল দিয়ে এখানে পাঠান।\n\n_চ্যাট শেষ করতে নিচের বাটনে ক্লিক করুন।_',
        'chat_close_btn': '❌ চ্যাট বন্ধ করুন',
        'chat_closed_msg': '✨ *ধন্যবাদ!*\n\nআমাদের সাথে যোগাযোগ করার জন্য আপনাকে অসংখ্য ধন্যবাদ। আপনার যেকোনো প্রয়োজনে আমরা সবসময় পাশে আছি। আপনার দিনটি শুভ হোক!',
        'contact_text': '🌟 *কন্টাক্ট ইনফরমেশন* 🌟\n━━━━━━━━━━━━━━━━━━━━━━\nযেকোনো প্রয়োজনে আমাদের সাথে যুক্ত হতে পারেন:\n\n📘 *Facebook:* [অফিসিয়াল পেজ](https://facebook.com)\n📱 *WhatsApp:* [মেসেজ দিন](https://wa.me/)\n✈️ *Telegram:* [অফিসিয়াল চ্যানেল](https://t.me/)\n📧 *Email:* support@vip-service.com\n📞 *Hotline:* +8801234567890\n━━━━━━━━━━━━━━━━━━━━━━\n_আমরা সর্বদা আপনার সেবায় নিয়োজিত!_',
        'no_exam_data': 'ℹ️ আপনার কোনো আসন্ন পরীক্ষার শিডিউল নেই।',
        'exam_info': '🎓 *এক্সাম শিডিউল*\n━━━━━━━━━━━━━━━━━━━━━━\n📖 *বিষয়:* {sub}\n📅 *তারিখ:* {date}\n⏰ *সময়:* {time}\n━━━━━━━━━━━━━━━━━━━━━━\n_পরীক্ষার অন্তত ১৫ মিনিট আগে প্রস্তুতি সম্পন্ন করুন।_'
    },
    'en': {
        'menu_chat': '💬 Live Support',
        'menu_apply': '📝 Service Request',
        'menu_docs': '📁 Essential Docs',
        'menu_embassy': '🏛️ Embassy Q&A',
        'menu_exam': '📅 Exam Schedule',
        'menu_contact': '📞 About Us',
        'menu_admin': '⚙️ Admin Panel',
        'not_approved': '⚠️ *Access Denied!*\nYour account is pending verification. Please wait.',
        'ask_name': '👤 *Enter your full name:*',
        'ask_wa': '📱 *Enter your active WhatsApp number:*',
        'cat_select': '🎯 *Select a service category:*',
        'req_sent': '✅ *Request Submitted Successfully!*\n\n🔖 Your Tracking Roll: `{roll}`\n\n_Our team will contact you shortly._',
        'chat_init': '🎧 *Welcome to VIP Support!*\n\nAn agent will join you shortly. Please explain your issue in detail or send relevant files.\n\n_Click the button below to end the chat._',
        'chat_close_btn': '❌ End Chat',
        'chat_closed_msg': '✨ *Thank You!*\n\nThank you for reaching out to us. We are always here to help. Have a great day!',
        'contact_text': '🌟 *Contact Information* 🌟\n━━━━━━━━━━━━━━━━━━━━━━\nFeel free to reach out:\n\n📘 *Facebook:* [Official Page](https://facebook.com)\n📱 *WhatsApp:* [Message Us](https://wa.me/)\n✈️ *Telegram:* [Official Channel](https://t.me/)\n📧 *Email:* support@vip-service.com\n📞 *Hotline:* +8801234567890\n━━━━━━━━━━━━━━━━━━━━━━\n_We are always here to help!_',
        'no_exam_data': 'ℹ️ You have no upcoming exams scheduled.',
        'exam_info': '🎓 *Exam Schedule*\n━━━━━━━━━━━━━━━━━━━━━━\n📖 *Subject:* {sub}\n📅 *Date:* {date}\n⏰ *Time:* {time}\n━━━━━━━━━━━━━━━━━━━━━━\n_Please be prepared at least 15 minutes prior._'
    }
}

# ==========================================
# 3. UTILITIES & VIP FEATURES
# ==========================================
def show_typing(chat_id):
    """বট রিপ্লাই দেওয়ার আগে একটু রিয়েলিস্টিক ফিল দেওয়ার জন্য"""
    try:
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(0.5)
    except:
        pass

def get_live_time(lang):
    bd_tz = pytz.timezone('Asia/Dhaka')
    ru_tz = pytz.timezone('Europe/Moscow')
    now_utc = datetime.datetime.now(pytz.utc)
    bd_time = now_utc.astimezone(bd_tz).strftime('%I:%M %p | %d %b %Y')
    ru_time = now_utc.astimezone(ru_tz).strftime('%I:%M %p | %d %b %Y')
    
    if lang == 'bn':
        return f"⏱ *লাইভ টাইম জোন*\n━━━━━━━━━━━━━━━━━━━━━━\n🇧🇩 *ঢাকা:* `{bd_time}`\n🇷🇺 *মস্কো:* `{ru_time}`\n━━━━━━━━━━━━━━━━━━━━━━\n"
    else:
        return f"⏱ *Live Timezone*\n━━━━━━━━━━━━━━━━━━━━━━\n🇧🇩 *Dhaka:* `{bd_time}`\n🇷🇺 *Moscow:* `{ru_time}`\n━━━━━━━━━━━━━━━━━━━━━━\n"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'VIP Bot Server is Live!')

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def is_admin(username):
    if not username:
        return False
    return username.lower() in [a.lower() for a in ADMINS]

# ==========================================
# 4. BOT START & MAIN MENU
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    show_typing(chat_id)
    
    if chat_id not in users_db:
        users_db[chat_id] = {'lang': 'bn', 'is_approved': False, 'roll': None, 'exam_dt': None}
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    bot.send_message(chat_id, "🌐 *Please select your preferred language:*\nআপনার পছন্দের ভাষা নির্বাচন করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['lang_bn', 'lang_en'])
def set_lang(call):
    chat_id = call.message.chat.id
    users_db[chat_id]['lang'] = 'bn' if call.data == 'lang_bn' else 'en'
    bot.delete_message(chat_id, call.message.message_id)
    show_main_menu(chat_id)

def show_main_menu(chat_id):
    show_typing(chat_id)
    u_data = users_db.get(chat_id, {'lang': 'bn', 'is_approved': False})
    lang = u_data['lang']
    t_dict = lang_dict[lang]
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # VIP Styled Buttons
    markup.add(t_dict['menu_chat'], t_dict['menu_apply'])
    
    if u_data.get('is_approved'):
        markup.add(t_dict['menu_docs'], t_dict['menu_embassy'])
        markup.add(t_dict['menu_exam'], t_dict['menu_contact'])
        
    try:
        if is_admin(bot.get_chat(chat_id).username):
            markup.add(t_dict['menu_admin'])
    except:
        pass

    header = get_live_time(lang)
    welcome_text = "✨ *মেইন মেনু* ✨\nনিচের অপশনগুলো থেকে আপনার প্রয়োজনীয় সেবাটি বেছে নিন:" if lang == 'bn' else "✨ *Main Menu* ✨\nChoose your required service below:"
    
    bot.send_message(chat_id, f"{header}\n{welcome_text}", reply_markup=markup)

# ==========================================
# 5. APPLY SERVICE (VIP Flow)
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_apply'], lang_dict['en']['menu_apply']])
def apply_service(message):
    chat_id = message.chat.id
    lang = users_db[chat_id]['lang']
    show_typing(chat_id)
    
    if users_db[chat_id].get('is_approved'):
        bot.send_message(chat_id, "✅ You are already a verified user!" if lang == 'en' else "✅ আপনি ইতিমধ্যেই একজন ভেরিফাইড ইউজার!")
        return

    temp_data[chat_id] = {}
    msg = bot.send_message(chat_id, lang_dict[lang]['ask_name'])
    bot.register_next_step_handler(msg, step_wa)

def step_wa(message):
    chat_id = message.chat.id
    temp_data[chat_id]['name'] = message.text
    show_typing(chat_id)
    msg = bot.send_message(chat_id, lang_dict[users_db[chat_id]['lang']]['ask_wa'])
    bot.register_next_step_handler(msg, step_cat)

def step_cat(message):
    chat_id = message.chat.id
    temp_data[chat_id]['wa'] = message.text
    show_typing(chat_id)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎓 Scholarship Support", callback_data="cat_sch"),
        types.InlineKeyboardButton("🤖 Technical Support", callback_data="cat_bot")
    )
    bot.send_message(chat_id, lang_dict[users_db[chat_id]['lang']]['cat_select'], reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ['cat_sch', 'cat_bot'])
def finish_apply(call):
    global roll_counter
    chat_id = call.message.chat.id
    lang = users_db[chat_id]['lang']
    roll_counter += 1
    roll = roll_counter
    
    users_db[chat_id]['roll'] = roll
    users_db[chat_id]['name'] = temp_data[chat_id]['name']
    cat = "Scholarship Support" if call.data == 'cat_sch' else "Technical Support"
    username = call.from_user.username or "Hidden"

    bot.edit_message_text(lang_dict[lang]['req_sent'].format(roll=roll), chat_id, call.message.message_id)

    # VIP Admin Notification format
    admin_txt = f"🚨 *NEW VIP REQUEST*\n━━━━━━━━━━━━━━━━\n👤 *Name:* {users_db[chat_id]['name']}\n🔖 *Roll:* `{roll}`\n📱 *WA:* `{temp_data[chat_id]['wa']}`\n🎯 *Category:* {cat}\n🔗 *User:* @{username} (`{chat_id}`)\n━━━━━━━━━━━━━━━━"
    
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"apprv_{chat_id}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_{chat_id}")
    )
    bot.send_message(BACKUP_GROUP_ID, admin_txt, message_thread_id=TOPIC_APPLY, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('apprv_') or c.data.startswith('rej_'))
def handle_approval(call):
    action, uid = call.data.split('_')
    uid = int(uid)

    if action == 'apprv':
        users_db[uid]['is_approved'] = True
        bot.edit_message_text(call.message.text + "\n\n✅ *STATUS: APPROVED*", call.message.chat.id, call.message.message_id)
        
        show_typing(uid)
        txt = "🎉 *Congratulations!*\nYour VIP access has been approved!" if users_db[uid]['lang'] == 'en' else "🎉 *অভিনন্দন!*\nআপনার একাউন্টটি সফলভাবে ভেরিফাই করা হয়েছে!"
        bot.send_message(uid, txt)
        show_main_menu(uid)
    else:
        bot.edit_message_text(call.message.text + "\n\n❌ *STATUS: REJECTED*", call.message.chat.id, call.message.message_id)

# ==========================================
# 6. LIVE CHAT SYSTEM (Pro Level)
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_chat'], lang_dict['en']['menu_chat']])
def start_live_chat(message):
    chat_id = message.chat.id
    show_typing(chat_id)
    lang = users_db.get(chat_id, {}).get('lang', 'bn')
    
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
    mk.add(lang_dict[lang]['chat_close_btn'])
    
    bot.send_message(chat_id, lang_dict[lang]['chat_init'], reply_markup=mk)
    users_db[chat_id]['in_chat'] = True

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['chat_close_btn'], lang_dict['en']['chat_close_btn']])
def user_close_chat(message):
    chat_id = message.chat.id
    roll = users_db.get(chat_id, {}).get('roll', 'N/A')
    users_db[chat_id]['in_chat'] = False
    show_typing(chat_id)
    
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("✅ Confirm Close", callback_data=f"closechat_{chat_id}"))
    bot.send_message(BACKUP_GROUP_ID, f"🛑 *Chat Closure Request*\nUser Roll: `{roll}` wants to close the session.", message_thread_id=TOPIC_SUPPORT, reply_markup=mk)
    show_main_menu(chat_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith('closechat_'))
def admin_confirm_close(call):
    uid = int(call.data.split('_')[1])
    lang = users_db.get(uid, {}).get('lang', 'bn')
    bot.send_message(uid, lang_dict[lang]['chat_closed_msg'])
    bot.edit_message_text("✅ Chat session closed securely.", call.message.chat.id, call.message.message_id)

@bot.message_handler(content_types=['text', 'photo', 'document'], func=lambda m: m.chat.type == 'private' and users_db.get(m.chat.id, {}).get('in_chat', False))
def forward_to_admin(message):
    chat_id = message.chat.id
    roll = users_db.get(chat_id, {}).get('roll', 'N/A')
    name = users_db.get(chat_id, {}).get('name', 'Client')
    
    caption = f"💬 *Live Chat* [Roll: `{roll}`]\n👤 Name: {name}\n🆔 ID: `{chat_id}`"
    
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton("🕒 Busy Mode", callback_data=f"chatbusy_{chat_id}"),
        types.InlineKeyboardButton("🟢 Join Session", callback_data=f"chatjoin_{chat_id}")
    )

    if message.content_type == 'text':
        bot.send_message(BACKUP_GROUP_ID, f"{caption}\n\n📝 *Message:* {message.text}", message_thread_id=TOPIC_SUPPORT, reply_markup=mk)
    elif message.content_type == 'photo':
        bot.send_photo(BACKUP_GROUP_ID, message.photo[-1].file_id, caption=caption, message_thread_id=TOPIC_SUPPORT, reply_markup=mk)
    elif message.content_type == 'document':
        bot.send_document(BACKUP_GROUP_ID, message.document.file_id, caption=caption, message_thread_id=TOPIC_SUPPORT, reply_markup=mk)
        
    # Note for support managers: Notifications can be synced to Slack channels here instead of Jira for better team communication.

@bot.callback_query_handler(func=lambda c: c.data.startswith('chatbusy_') or c.data.startswith('chatjoin_'))
def admin_chat_action(call):
    action, uid = call.data.split('_')
    uid = int(uid)
    lang = users_db.get(uid, {}).get('lang', 'bn')

    if action == 'chatbusy':
        txt = "Our agents are currently busy. Please leave your detailed message." if lang == 'en' else "আমাদের সাপোর্ট এজেন্টরা এই মুহূর্তে ব্যস্ত আছেন। আপনার বিস্তারিত মেসেজটি দিয়ে রাখুন, আমরা শীঘ্রই চেক করছি।"
        bot.send_message(uid, txt)
    else:
        txt = "👨‍💻 An agent has joined the chat. How can we assist you today?" if lang == 'en' else "👨‍💻 একজন সাপোর্ট এজেন্ট চ্যাটে যুক্ত হয়েছেন। আপনাকে কীভাবে সাহায্য করতে পারি?"
        bot.send_message(uid, txt)
    
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.message_handler(func=lambda m: m.chat.id == BACKUP_GROUP_ID and m.message_thread_id == TOPIC_SUPPORT and m.reply_to_message)
def admin_reply(message):
    try:
        import re
        reply_txt = message.reply_to_message.text or message.reply_to_message.caption
        match = re.search(r'ID: `(\d+)`', reply_txt)
        if match:
            target_id = int(match.group(1))
            show_typing(target_id)
            if message.content_type == 'text':
                bot.send_message(target_id, f"🎧 *Support Team:*\n{message.text}")
            elif message.content_type == 'photo':
                bot.send_photo(target_id, message.photo[-1].file_id, caption=f"🎧 *Support Team:*\n{message.caption or ''}")
            elif message.content_type == 'document':
                bot.send_document(target_id, message.document.file_id, caption=f"🎧 *Support Team:*\n{message.caption or ''}")
    except:
        pass

# ==========================================
# 7. INFO MENUS (Docs, Embassy, Exam)
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_contact'], lang_dict['en']['menu_contact']])
def show_contact(message):
    show_typing(message.chat.id)
    bot.send_message(message.chat.id, lang_dict[users_db[message.chat.id]['lang']]['contact_text'], disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_exam'], lang_dict['en']['menu_exam']])
def show_exam(message):
    uid = message.chat.id
    show_typing(uid)
    lang = users_db[uid]['lang']
    if not users_db[uid].get('exam_sub'):
        bot.send_message(uid, lang_dict[lang]['no_exam_data'])
    else:
        bot.send_message(uid, lang_dict[lang]['exam_info'].format(sub=users_db[uid]['exam_sub'], date=users_db[uid]['exam_date'], time=users_db[uid]['exam_time']))

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_docs'], lang_dict['en']['menu_docs']])
def show_docs(message):
    show_typing(message.chat.id)
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("🇷🇺 Self Fund Docs", callback_data="doc_self"),
        types.InlineKeyboardButton("🎓 Scholarship Docs", callback_data="doc_sch"),
        types.InlineKeyboardButton("🏛️ Embassy Docs", callback_data="doc_emb")
    )
    bot.send_message(message.chat.id, "📂 *Choose Document Category:*", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('doc_'))
def doc_details(call):
    if call.data == 'doc_self':
        txt = "🇷🇺 *Self Fund Checklist*\n\n1️⃣ Academy Marksheet\n2️⃣ Passport Copy\n3️⃣ Certificate Apostille\n4️⃣ Financial Affidavit\n5️⃣ 3.5x4.5 Lab Print Photo"
    elif call.data == 'doc_sch':
        txt = "🎓 *Scholarship Checklist*\n\n1️⃣ Academy Marksheet\n2️⃣ Valid Passport\n3️⃣ Active Phone Number\n4️⃣ Certificate Apostille\n5️⃣ Passport Size Photo & Signature"
    else:
        txt = "🏛️ *Embassy Checklist*\n\n1️⃣ Ministry Approval Letter\n2️⃣ Visa Application Form\n3️⃣ Original Diploma\n4️⃣ Medical Fitness Certificate\n5️⃣ Marksheet + Apostille\n6️⃣ Original Passport + Copy"
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_embassy'], lang_dict['en']['menu_embassy']])
def show_embassy(message):
    show_typing(message.chat.id)
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("❓ Why Russia?", callback_data="qa_russia"),
        types.InlineKeyboardButton("❓ Why this University?", callback_data="qa_uni"),
        types.InlineKeyboardButton("❓ Who is your sponsor?", callback_data="qa_sponsor")
    )
    bot.send_message(message.chat.id, "🏛️ *Embassy Interview Masterclass*", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('qa_'))
def qa_details(call):
    if call.data == 'qa_russia':
        ans = "💡 Answer: Russia provides top-tier education with globally accepted degrees, all within an affordable living cost structure."
    elif call.data == 'qa_uni':
        ans = "💡 Answer: It is one of the most prestigious universities, aligning perfectly with my academic goals and offering an excellent curriculum."
    else:
        ans = "💡 Answer: My father is my sponsor. He runs a successful business..."
    bot.answer_callback_query(call.id, ans, show_alert=True)

# ==========================================
# 8. SUPER ADMIN PANEL
# ==========================================
@bot.message_handler(func=lambda m: m.text in [lang_dict['bn']['menu_admin'], lang_dict['en']['menu_admin']])
def admin_panel(message):
    if not is_admin(message.from_user.username):
        return
    show_typing(message.chat.id)
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton("👥 Manage VIP Users", callback_data="adm_users"),
        types.InlineKeyboardButton("📅 Setup Exam Schedule", callback_data="adm_exam"),
        types.InlineKeyboardButton("📢 Broadcast Notice", callback_data="adm_notice")
    )
    bot.send_message(message.chat.id, "🛠️ *Super Admin Dashboard*", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith('adm_'))
def admin_panel_actions(call):
    chat_id = call.message.chat.id
    if call.data == 'adm_users':
        if not users_db:
            bot.answer_callback_query(call.id, "No data found!", show_alert=True)
            return
        user_list = "👥 *VIP Users List:*\n━━━━━━━━━━━━━━━━\n"
        for uid, data in users_db.items():
            if data.get('is_approved'):
                user_list += f"🔖 Roll: `{data.get('roll')}` | 👤 {data.get('name', 'Unknown')}\n"
        bot.send_message(chat_id, user_list)
        bot.answer_callback_query(call.id)

    elif call.data == 'adm_exam':
        msg = bot.send_message(chat_id, "📅 *শিডিউল ফর্মেট:*\n`রোল, সাবজেক্ট, তারিখ (DD-MM-YYYY), সময় (HH:MM AM/PM)`\n\nউদাহরণ: `10001, Math, 25-12-2026, 10:00 AM`")
        bot.register_next_step_handler(msg, process_exam_setup)

    elif call.data == 'adm_notice':
        mk = types.InlineKeyboardMarkup()
        mk.add(
            types.InlineKeyboardButton("🎉 Success/Congrats", callback_data="notice_congrats"),
            types.InlineKeyboardButton("📢 Urgent Alert", callback_data="notice_general")
        )
        bot.send_message(chat_id, "Select Notice Type:", reply_markup=mk)

def process_exam_setup(message):
    try:
        parts = [p.strip() for p in message.text.split(',')]
        roll, subject, date_str, time_str = int(parts[0]), parts[1], parts[2], parts[3]
        exam_dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %I:%M %p")
        
        updated = False
        for uid, data in users_db.items():
            if data.get('roll') == roll:
                users_db[uid].update({'exam_sub': subject, 'exam_date': date_str, 'exam_time': time_str, 'exam_dt': exam_dt})
                updated = True
                bot.send_message(uid, f"🔔 *Exam Alert!*\n\nYour *{subject}* exam is scheduled on {date_str} at {time_str}.")
                break
        
        txt = "✅ শিডিউল আপডেট সফল!" if updated else "❌ ইউজার পাওয়া যায়নি।"
        bot.send_message(message.chat.id, txt)
    except:
        bot.send_message(message.chat.id, "❌ ফর্মেট ভুল। আবার চেষ্টা করুন।")

@bot.callback_query_handler(func=lambda c: c.data.startswith('notice_'))
def ask_notice_text(call):
    n_type = "🎉 *Good News!*\n\n" if call.data == 'notice_congrats' else "🚨 *Important Notice!*\n\n"
    msg = bot.send_message(call.message.chat.id, "📝 Send the notice text or image with caption:")
    bot.register_next_step_handler(msg, send_notice_to_all, n_type)

def send_notice_to_all(message, notice_type):
    count = 0
    for uid, data in users_db.items():
        if data.get('is_approved'):
            try:
                if message.content_type == 'text':
                    bot.send_message(uid, f"{notice_type}{message.text}")
                elif message.content_type == 'photo':
                    bot.send_photo(uid, message.photo[-1].file_id, caption=f"{notice_type}{message.caption or ''}")
                count += 1
            except:
                pass
    bot.send_message(message.chat.id, f"✅ Broadcast sent successfully to {count} users.")

# ==========================================
# 9. SMART ALERTS THREAD
# ==========================================
def exam_alert_thread():
    while True:
        now = datetime.datetime.now()
        for uid, data in users_db.items():
            if data.get('exam_dt'):
                dt = data['exam_dt']
                diff = (dt - now).total_seconds()
                if 3540 <= diff <= 3600:
                    bot.send_message(uid, "⚠️ *URGENT REMINDER*\nYour exam will start in exactly 1 Hour. Please get ready!")
                    data['exam_dt'] = None 
        time.sleep(60)

# ==========================================
# RUN VIP BOT
# ==========================================
if __name__ == "__main__":
    t1 = threading.Thread(target=run_web_server)
    t1.daemon = True
    t1.start()

    t2 = threading.Thread(target=exam_alert_thread)
    t2.daemon = True
    t2.start()

    print("🚀 VIP Bot Server Started Successfully...")
    bot.infinity_polling()
