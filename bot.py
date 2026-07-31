import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import time
import pytz
import telebot
from telebot import types

# ==========================================
# 1. CONFIGURATION & SETUP
# ==========================================
API_TOKEN = "8683150922:AAFBcqOyG6YugrzfL6u3nRmu9zz9yJwqiDc"
bot = telebot.TeleBot(API_TOKEN)

ADMINS = ["alamin_041", "aminal041"]
BACKUP_GROUP_ID = -1003210815541
TOPIC_SUPPORT = 5
TOPIC_APPLY = 9

# Database simulation (In-memory)
users_db = {}
temp_data = {}
roll_counter = 10000

# ==========================================
# 2. MULTI-LANGUAGE DICTIONARY
# ==========================================
lang_dict = {
    'bn': {
        'menu_chat': '💬 Live Chat',
        'menu_apply': '📝 Apply Service',
        'menu_docs': '📁 Documents',
        'menu_embassy': '🏛️ Embassy Q&A',
        'menu_exam': '📅 Exam Schedule',
        'menu_contact': '📞 Contact Details',
        'menu_admin': '🛠️ Admin Panel',
        'not_approved': (
            '❌ আপনার একাউন্ট এখনও অ্যাপ্রুভ হয়নি। দয়া করে অপেক্ষা'
            ' করুন।'
        ),
        'ask_name': 'আপনার পূর্ণাঙ্গ নাম লিখুন:',
        'ask_wa': 'আপনার WhatsApp নম্বর দিন:',
        'cat_select': 'সার্ভিস ক্যাটেগরি নির্বাচন করুন:',
        'req_sent': (
            '✅ আপনার রিকুয়েষ্ট পাঠানো হয়েছে।\nআপনার রোল নাম্বার: {roll}'
        ),
        'chat_init': (
            '💬 লাইভ চ্যাট শুরু হয়েছে। আপনার মেসেজ বা ফাইল পাঠান। চ্যাট শেষ করতে'
            " উপরের 'Chat Close' বাটনে ক্লিক করুন।"
        ),
        'chat_close_btn': '❌ Chat Close',
        'chat_closed_msg': (
            'সময় ও আমাদের সাথে থাকার জন্য আপনাকে অসংখ্য ধন্যবাদ। পরবর্তীতে কোন'
            ' সমস্যা হলে আমাদের সাথে অবশ্যই যোগাযোগ করবেন। আপনার জন্য শুভকামনা'
            ' রইল!'
        ),
        'contact_text': (
            '🌟 *যোগাযোগ করুন* 🌟\n\nযেকোনো প্রয়োজনে আমাদের সাথে যুক্ত হতে'
            ' পারেন:\n\n📘 Facebook:'
            ' [Click Here](https://facebook.com)\n📱 WhatsApp:'
            ' [Click Here](https://wa.me/)\n✈️ Telegram:'
            ' [Click Here](https://t.me/)\n📧 Email:'
            ' support@example.com\n📞 Phone: +8801234567890\n\n_আমরা সর্বদা'
            ' আপনার সেবায় নিয়োজিত!_'
        ),
        'no_exam_data': '❌ আপনার পরীক্ষার কোনো শিডিউল পাওয়া যায়নি।',
        'exam_info': (
            '📚 *আপনার পরীক্ষার শিডিউল*\n\n📖 বিষয়: {sub}\n📅 তারিখ: {date}\n⏰'
            ' সময়: {time}'
        ),
    },
    'en': {
        'menu_chat': '💬 Live Chat',
        'menu_apply': '📝 Apply Service',
        'menu_docs': '📁 Documents',
        'menu_embassy': '🏛️ Embassy Q&A',
        'menu_exam': '📅 Exam Schedule',
        'menu_contact': '📞 Contact Details',
        'menu_admin': '🛠️ Admin Panel',
        'not_approved': '❌ Your account is not approved yet. Please wait.',
        'ask_name': 'Please enter your full name:',
        'ask_wa': 'Please enter your WhatsApp number:',
        'cat_select': 'Select a service category:',
        'req_sent': (
            '✅ Your request has been sent.\nYour Roll Number: {roll}'
        ),
        'chat_init': (
            "💬 Live chat started. Send your message/file. Click 'Chat Close'"
            ' above to end.'
        ),
        'chat_close_btn': '❌ Chat Close',
        'chat_closed_msg': (
            'Thank you so much for your time and for staying with us. Contact'
            ' us for any future issues. Best wishes to you!'
        ),
        'contact_text': (
            '🌟 *Contact Us* 🌟\n\nFeel free to reach out:\n\n📘 Facebook:'
            ' [Click Here](https://facebook.com)\n📱 WhatsApp:'
            ' [Click Here](https://wa.me/)\n✈️ Telegram:'
            ' [Click Here](https://t.me/)\n📧 Email:'
            ' support@example.com\n📞 Phone: +8801234567890\n\n_We are always'
            ' here to help!_'
        ),
        'no_exam_data': '❌ No exam schedule found for you.',
        'exam_info': (
            '📚 *Your Exam Schedule*\n\n📖 Subject: {sub}\n📅 Date: {date}\n⏰'
            ' Time: {time}'
        ),
    },
}


# ==========================================
# 3. UTILITIES & DUMMY SERVER
# ==========================================
def get_live_time(lang):
  bd_tz = pytz.timezone('Asia/Dhaka')
  ru_tz = pytz.timezone('Europe/Moscow')
  now_utc = datetime.datetime.now(pytz.utc)
  bd_time = now_utc.astimezone(bd_tz).strftime('%d %B %Y, %I:%M %p')
  ru_time = now_utc.astimezone(ru_tz).strftime('%d %B %Y, %I:%M %p')

  if lang == 'bn':
    return (
        f'⏰ *বর্তমান সময়:*\n━━━━━━━━━━━━━━━\n🇧🇩 বাংলাদেশ:'
        f' `{bd_time}`\n🇷🇺 রাশিয়া: `{ru_time}`\n━━━━━━━━━━━━━━━\n'
    )
  else:
    return (
        f'⏰ *Current Time:*\n━━━━━━━━━━━━━━━\n🇧🇩 BD: `{bd_time}`\n🇷🇺 RU:'
        f' `{ru_time}`\n━━━━━━━━━━━━━━━\n'
    )


class SimpleHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b'Bot is running!')


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
  if chat_id not in users_db:
    users_db[chat_id] = {
        'lang': 'bn',
        'is_approved': False,
        'roll': None,
        'exam_dt': None,
    }

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton('🇧🇩 বাংলা', callback_data='lang_bn'),
      types.InlineKeyboardButton('🇬🇧 English', callback_data='lang_en'),
  )
  bot.send_message(
      chat_id, 'ভাষা নির্বাচন করুন / Select Language:', reply_markup=markup
  )


@bot.callback_query_handler(func=lambda call: call.data in ['lang_bn', 'lang_en'])
def set_lang(call):
  chat_id = call.message.chat.id
  lang = 'bn' if call.data == 'lang_bn' else 'en'
  users_db[chat_id]['lang'] = lang
  bot.delete_message(chat_id, call.message.message_id)
  show_main_menu(chat_id)


def show_main_menu(chat_id):
  u_data = users_db.get(chat_id, {'lang': 'bn', 'is_approved': False})
  lang = u_data['lang']
  t_dict = lang_dict[lang]

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

  # Always visible
  markup.add(t_dict['menu_chat'], t_dict['menu_apply'])

  # Visible only if approved
  if u_data.get('is_approved'):
    markup.add(t_dict['menu_docs'], t_dict['menu_embassy'])
    markup.add(t_dict['menu_exam'], t_dict['menu_contact'])

  # Visible only to admins
  try:
    username = bot.get_chat(chat_id).username
    if is_admin(username):
      markup.add(t_dict['menu_admin'])
  except Exception:
    pass

  header = get_live_time(lang)
  bot.send_message(
      chat_id,
      header + '\nমেনু থেকে নির্বাচন করুন:',
      parse_mode='Markdown',
      reply_markup=markup,
  )


# ==========================================
# 5. APPLY SERVICE
# ==========================================
@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_apply'], lang_dict['en']['menu_apply']]
)
def apply_service(message):
  chat_id = message.chat.id
  lang = users_db[chat_id]['lang']
  if users_db[chat_id].get('is_approved'):
    bot.send_message(
        chat_id,
        'You are already approved!'
        if lang == 'en'
        else 'আপনি ইতিমধ্যেই অ্যাপ্রুভড!',
    )
    return

  temp_data[chat_id] = {}
  msg = bot.send_message(chat_id, lang_dict[lang]['ask_name'])
  bot.register_next_step_handler(msg, step_wa)


def step_wa(message):
  chat_id = message.chat.id
  temp_data[chat_id]['name'] = message.text
  msg = bot.send_message(
      chat_id, lang_dict[users_db[chat_id]['lang']]['ask_wa']
  )
  bot.register_next_step_handler(msg, step_cat)


def step_cat(message):
  chat_id = message.chat.id
  temp_data[chat_id]['wa'] = message.text

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          'Scholarship Support', callback_data='cat_sch'
      ),
      types.InlineKeyboardButton('Bot Support', callback_data='cat_bot'),
  )
  bot.send_message(
      chat_id,
      lang_dict[users_db[chat_id]['lang']]['cat_select'],
      reply_markup=markup,
  )


@bot.callback_query_handler(func=lambda c: c.data in ['cat_sch', 'cat_bot'])
def finish_apply(call):
  global roll_counter
  chat_id = call.message.chat.id
  lang = users_db[chat_id]['lang']

  roll_counter += 1
  roll = roll_counter
  users_db[chat_id]['roll'] = roll
  users_db[chat_id]['name'] = temp_data[chat_id]['name']

  cat = 'Scholarship Support' if call.data == 'cat_sch' else 'Bot Support'
  username = call.from_user.username or 'No Username'

  # Notify User
  bot.edit_message_text(
      lang_dict[lang]['req_sent'].format(roll=roll),
      chat_id,
      call.message.message_id,
  )

  # Send to Admin Topic 9
  admin_txt = (
      f'📝 *Apply Service Request*\n\nRoll: `{roll}`\nName:'
      f' {users_db[chat_id]["name"]}\nWA: {temp_data[chat_id]["wa"]}\nCategory:'
      f' {cat}\nUser: @{username} (`{chat_id}`)'
  )

  mk = types.InlineKeyboardMarkup()
  mk.add(
      types.InlineKeyboardButton(
          '✅ Approved', callback_data=f'apprv_{chat_id}'
      ),
      types.InlineKeyboardButton('❌ Rejected', callback_data=f'rej_{chat_id}'),
  )

  bot.send_message(
      BACKUP_GROUP_ID,
      admin_txt,
      parse_mode='Markdown',
      message_thread_id=TOPIC_APPLY,
      reply_markup=mk,
  )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith('apprv_') or c.data.startswith('rej_')
)
def handle_approval(call):
  action, uid = call.data.split('_')
  uid = int(uid)

  if action == 'apprv':
    users_db[uid]['is_approved'] = True
    bot.edit_message_text(
        call.message.text + '\n\n✅ *Status: APPROVED*',
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
    )
    lang = users_db[uid]['lang']
    txt = (
        'Your service request has been APPROVED!'
        if lang == 'en'
        else 'আপনার সার্ভিস রিকোয়েস্ট Approved করা হয়েছে!'
    )
    bot.send_message(uid, txt)
    show_main_menu(uid)
  else:
    bot.edit_message_text(
        call.message.text + '\n\n❌ *Status: REJECTED*',
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown',
    )


# ==========================================
# 6. LIVE CHAT SYSTEM
# ==========================================
@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_chat'], lang_dict['en']['menu_chat']]
)
def start_live_chat(message):
  chat_id = message.chat.id
  lang = users_db.get(chat_id, {}).get('lang', 'bn')

  mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
  mk.add(lang_dict[lang]['chat_close_btn'])

  bot.send_message(chat_id, lang_dict[lang]['chat_init'], reply_markup=mk)
  users_db[chat_id]['in_chat'] = True


@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['chat_close_btn'], lang_dict['en']['chat_close_btn']]
)
def user_close_chat(message):
  chat_id = message.chat.id
  roll = users_db.get(chat_id, {}).get('roll', 'Unknown')
  users_db[chat_id]['in_chat'] = False

  mk = types.InlineKeyboardMarkup()
  mk.add(
      types.InlineKeyboardButton(
          '✅ Confirm Close (OK)', callback_data=f'closechat_{chat_id}'
      )
  )
  bot.send_message(
      BACKUP_GROUP_ID,
      f'🛑 User Roll: {roll} requested to close the chat.',
      message_thread_id=TOPIC_SUPPORT,
      reply_markup=mk,
  )

  show_main_menu(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith('closechat_'))
def admin_confirm_close(call):
  uid = int(call.data.split('_')[1])
  lang = users_db.get(uid, {}).get('lang', 'bn')
  bot.send_message(uid, lang_dict[lang]['chat_closed_msg'])
  bot.edit_message_text(
      '✅ Chat closed successfully.', call.message.chat.id, call.message.message_id
  )


# Forward user msgs to Topic 5
@bot.message_handler(
    content_types=['text', 'photo', 'document'],
    func=lambda m: m.chat.type == 'private'
    and users_db.get(m.chat.id, {}).get('in_chat', False),
)
def forward_to_admin(message):
  chat_id = message.chat.id
  roll = users_db.get(chat_id, {}).get('roll', 'N/A')
  name = users_db.get(chat_id, {}).get('name', 'N/A')

  caption = f'💬 [Roll: {roll}] {name}\nID: `{chat_id}`'

  mk = types.InlineKeyboardMarkup()
  mk.add(
      types.InlineKeyboardButton(
          '🕒 Busy', callback_data=f'chatbusy_{chat_id}'
      ),
      types.InlineKeyboardButton(
          '🟢 Join Now', callback_data=f'chatjoin_{chat_id}'
      ),
  )

  if message.content_type == 'text':
    bot.send_message(
        BACKUP_GROUP_ID,
        f'{caption}\n\n{message.text}',
        message_thread_id=TOPIC_SUPPORT,
        reply_markup=mk,
    )
  elif message.content_type == 'photo':
    bot.send_photo(
        BACKUP_GROUP_ID,
        message.photo[-1].file_id,
        caption=caption,
        message_thread_id=TOPIC_SUPPORT,
        reply_markup=mk,
    )
  elif message.content_type == 'document':
    bot.send_document(
        BACKUP_GROUP_ID,
        message.document.file_id,
        caption=caption,
        message_thread_id=TOPIC_SUPPORT,
        reply_markup=mk,
    )


@bot.callback_query_handler(
    func=lambda c: c.data.startswith('chatbusy_')
    or c.data.startswith('chatjoin_')
)
def admin_chat_action(call):
  action, uid = call.data.split('_')
  uid = int(uid)
  lang = users_db.get(uid, {}).get('lang', 'bn')

  if action == 'chatbusy':
    txt = (
        'We are currently busy. Please leave your message, we will reply soon.'
        if lang == 'en'
        else (
            'আমরা বর্তমানে একটু ব্যস্ত আছি। দয়া করে আপনার মেসেজ দিয়ে রাখুন,'
            ' শীঘ্রই রিপ্লাই দেওয়া হবে।'
        )
    )
    bot.send_message(uid, txt)
  else:
    txt = (
        'Admin joined the chat. Please explain your issue in detail.'
        if lang == 'en'
        else (
            'এডমিন চ্যাটে জয়েন করেছেন। দয়া করে আপনার সমস্যাটি বিস্তারিত'
            ' বলুন।'
        )
    )
    bot.send_message(uid, txt)

  bot.edit_message_reply_markup(
      call.message.chat.id, call.message.message_id, reply_markup=None
  )


# Admin replies to User
@bot.message_handler(
    func=lambda m: m.chat.id == BACKUP_GROUP_ID
    and m.message_thread_id == TOPIC_SUPPORT
    and m.reply_to_message
)
def admin_reply(message):
  try:
    import re

    reply_txt = (
        message.reply_to_message.text or message.reply_to_message.caption
    )
    match = re.search(r'ID: `(\d+)`', reply_txt)
    if match:
      target_id = int(match.group(1))
      if message.content_type == 'text':
        bot.send_message(
            target_id, f'👨‍💻 *Admin:* {message.text}', parse_mode='Markdown'
        )
      elif message.content_type == 'photo':
        bot.send_photo(
            target_id,
            message.photo[-1].file_id,
            caption='👨‍💻 *Admin:* ' + (message.caption or ''),
            parse_mode='Markdown',
        )
      elif message.content_type == 'document':
        bot.send_document(
            target_id,
            message.document.file_id,
            caption='👨‍💻 *Admin:* ' + (message.caption or ''),
            parse_mode='Markdown',
        )
  except Exception:
    pass


# ==========================================
# 7. MENU: CONTACT, EXAM, DOCS, EMBASSY
# ==========================================
@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_contact'], lang_dict['en']['menu_contact']]
)
def show_contact(message):
  lang = users_db[message.chat.id]['lang']
  bot.send_message(
      message.chat.id,
      lang_dict[lang]['contact_text'],
      parse_mode='Markdown',
      disable_web_page_preview=True,
  )


@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_exam'], lang_dict['en']['menu_exam']]
)
def show_exam(message):
  uid = message.chat.id
  lang = users_db[uid]['lang']
  if not users_db[uid].get('exam_sub'):
    bot.send_message(uid, lang_dict[lang]['no_exam_data'])
  else:
    txt = lang_dict[lang]['exam_info'].format(
        sub=users_db[uid]['exam_sub'],
        date=users_db[uid]['exam_date'],
        time=users_db[uid]['exam_time'],
    )
    bot.send_message(uid, txt, parse_mode='Markdown')


@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_docs'], lang_dict['en']['menu_docs']]
)
def show_docs(message):
  mk = types.InlineKeyboardMarkup(row_width=1)
  mk.add(
      types.InlineKeyboardButton(
          '🇷🇺 রাশিয়া Self fund', callback_data='doc_self'
      ),
      types.InlineKeyboardButton(
          '🇷🇺 Russia Scholarship', callback_data='doc_sch'
      ),
      types.InlineKeyboardButton(
          '🏛️ Embassy Document', callback_data='doc_emb'
      ),
  )
  bot.send_message(message.chat.id, 'Select Document Category:', reply_markup=mk)


@bot.callback_query_handler(func=lambda c: c.data.startswith('doc_'))
def doc_details(call):
  if call.data == 'doc_self':
    txt = (
        '🇷🇺 *Self fund Documents:*\n1. Academy marksheet\n2. Passport\n3.'
        ' Certificate Apostille\n4. AFFIDAVIT\n5. Photo 3.5x4.5 lab print'
    )
  elif call.data == 'doc_sch':
    txt = (
        '🇷🇺 *Scholarship Documents:*\n1. Academy marksheet\n2. Passport\n3.'
        ' Phone Number\n4. Certificate Apostille\n5. Photo & Signature'
    )
  else:
    txt = (
        '🏛️ *Embassy Documents:*\n1. Minister letter\n2. Application Form\n3.'
        ' Diploma\n4. Medical Certificate\n5. Marksheet + Apostille\n6.'
        ' Passport Copy + Original'
    )
  bot.edit_message_text(
      txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown'
  )


@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_embassy'], lang_dict['en']['menu_embassy']]
)
def show_embassy(message):
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        types.InlineKeyboardButton('Q: Why you are here?', callback_data='qa_1'),
        types.InlineKeyboardButton('Q: What is your name?', callback_data='qa_2'),
        types.InlineKeyboardButton('Q: What is your passport number?', callback_data='qa_3'),
        types.InlineKeyboardButton('Q: your date of birth?', callback_data='qa_4'),
        types.InlineKeyboardButton('Q: Introduce yourself/about yourself?', callback_data='qa_5'),
        types.InlineKeyboardButton('Q: Why Russia? Why not Other Countries?', callback_data='qa_6'),
        types.InlineKeyboardButton('Q: Why this University? Why not your present University? Why not India?', callback_data='qa_7'),
        types.InlineKeyboardButton('Q: Do you have any relatives in Russia?', callback_data='qa_8'),
        types.InlineKeyboardButton('Q: Do you have any friends in Russia?', callback_data='qa_9'),
        types.InlineKeyboardButton('Q: What will you do in your vacations in Russia?', callback_data='qa_10'),
        types.InlineKeyboardButton('Q: Who is your sponsor (tell excetly written on avedefit)?', callback_data='qa_11'),
        types.InlineKeyboardButton('Q: How do you know this University?', callback_data='qa_12'),
        types.InlineKeyboardButton('Q: What is your University name?', callback_data='qa_13'),
        types.InlineKeyboardButton('Q: About your University?', callback_data='qa_14'),
        types.InlineKeyboardButton('Q: About your subject?', callback_data='qa_15'),
        types.InlineKeyboardButton('Q: Tell me about your scholarship journey...', callback_data='qa_16'),
    )
    bot.send_message(
        message.chat.id,
        '🏛️ *Embassy Interview Q&A*',
        parse_mode='Markdown',
        reply_markup=mk,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('qa_'))
def qa_details(call):
    if call.data == 'qa_1':
        ans = 'A: I am here to face my interview.'
    elif call.data == 'qa_2':
        ans = 'A: My name is Md Amin.'
    elif call.data == 'qa_3':
        ans = 'A: A1104***93, Sir.'
    elif call.data == 'qa_4':
        ans = 'A: Second January 20**..'
    elif call.data == 'qa_5':
        ans = ('A: Thank you sir. My name is Mohammad Amin khan. I born in Chandpur and live in Dhaka for the purpose of study. '
               'I have completed my secondary education in 2019 with GPA 3.90 and later in 2021 i have completed my higher secondary education with GPA 4.83. '
               "Now I'm studying in Bangabondhu Sheikh Mujibur Rahman Science and Technology University. I'm an energetic and quick learner person. "
               'I have several skills like web development, computer skill, internet browsing and so on. My favorite hobbies are playing outdoor game, '
               'watching movies and solving difficult task. I want to be a business man. That\'s all about myself..')
    elif call.data == 'qa_6':
        ans = ('A: Thank you sir for asking me this question. Russia provides best quality education. Russian degree is accepted all over the world '
               'and educational and living cost is affordable for me. That\'s why I have chosen Russia..')
    elif call.data == 'qa_7':
        ans = ('A: Why this University?\nThank you sir for asking me this question. This University is one of the oldest Universities in Russia. '
               'Course they offer me matches with my previous study and Tuition fee is affordable for my parents.\n\n'
               'Why not your present University?\nActually Sir, I have a dream to study in Abroad. To be honest I am not satisfied in my present University.\n\n'
               'Why not india?\nTo be honest i think there is no difference between Bangladesh and Indian education system, life style and culture.')
    elif call.data == 'qa_8':
        ans = 'A: No sir.'
    elif call.data == 'qa_9':
        ans = 'A: Yes sir, i have some Facebook friends in this University.'
    elif call.data == 'qa_10':
        ans = 'A: I will visit other state in Russia to see the beautiful place of Russia.'
    elif call.data == 'qa_11':
        ans = ('A: Thank you sir. My father is my sponsor. He is a businessman. He has Restaurant business, Super Shop business and Transport business. '
               'His yearly income from businesses, House rent Transport business, and agricultural land around 60 Lac BDT.')
    elif call.data == 'qa_12':
        ans = 'A: I come to know this University from their University website and some of my Facebook friends are studying in this University also.'
    elif call.data == 'qa_13':
    ...
        ans = 'A: Thank you sir. My University name is Kursk State University.'
    elif call.data == 'qa_14':
        ans = ('A: Kursk State University is Kursk\'s oldest higher educational institution, founded in 1934 as Kursk State Pedagogical Institute, '
               'later in 1994 transformed into Kursk State Pedagogical University and has a current status since 2003. '
               'Kursk State University is a scientific, educational and cultural center of the region. The University offers a wide range of specialties, '
               'modern educational technologies, and various forms of professional training.')
    elif call.data == 'qa_15':
        ans = ('A: My major is Marketing.\nMarketing is a process by which companies create value for customers and build strong customer '
               'relationships to capture value from customers in return.\nMarketing is the act of satisfying and retaining customers.')
    elif call.data == 'qa_16':
        ans = 'A: Here is your scholarship journey and subject details based on your preparation.'
    else:
        ans = 'A: Information not available.'

    bot.answer_callback_query(call.id, ans, show_alert=True)


# ==========================================
# 8. ADMIN PANEL & NOTICES
# ==========================================
@bot.message_handler(
    func=lambda m: m.text
    in [lang_dict['bn']['menu_admin'], lang_dict['en']['menu_admin']]
)
def admin_panel(message):
  if not is_admin(message.from_user.username):
    return
  mk = types.InlineKeyboardMarkup(row_width=1)
  mk.add(
      types.InlineKeyboardButton(
          '👥 User Details', callback_data='adm_users'
      ),
      types.InlineKeyboardButton(
          '📅 Exam Schedule Set', callback_data='adm_exam'
      ),
      types.InlineKeyboardButton(
          '📢 All User Notice', callback_data='adm_notice'
      ),
  )
  bot.send_message(
      message.chat.id, '🛠️ *Admin Panel*', parse_mode='Markdown', reply_markup=mk
  )


@bot.callback_query_handler(func=lambda c: c.data.startswith('adm_'))
def admin_panel_actions(call):
  chat_id = call.message.chat.id

  # 1. User Details
  if call.data == 'adm_users':
    if not users_db:
      bot.answer_callback_query(
          call.id, 'কোনো ইউজার ডাটা নেই!', show_alert=True
      )
      return

    user_list = '👥 *Approved Users List:*\n\n'
    for uid, data in users_db.items():
      if data.get('is_approved'):
        user_list += (
            f"Roll: `{data.get('roll')}` | Name: {data.get('name', 'Unknown')}\n"
        )

    bot.send_message(chat_id, user_list, parse_mode='Markdown')
    bot.answer_callback_query(call.id)

  # 2. Exam Schedule Set
  elif call.data == 'adm_exam':
    msg = bot.send_message(
        chat_id,
        '📅 পরীক্ষার শিডিউল সেট করতে নিচের ফরমেটে মেসেজ'
        ' দিন:\n\n`রোল, সাবজেক্ট, তারিখ (DD-MM-YYYY), সময় (HH:MM'
        ' AM/PM)`\n\nউদাহরণ: `10001, Math, 25-12-2026, 10:00 AM`',
        parse_mode='Markdown',
    )
    bot.register_next_step_handler(msg, process_exam_setup)

  # 3. All User Notice
  elif call.data == 'adm_notice':
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton(
            '🥳 অভিনন্দন বার্তা', callback_data='notice_congrats'
        ),
        types.InlineKeyboardButton(
            '📢 সাধারণ নোটিশ', callback_data='notice_general'
        ),
    )
    bot.send_message(
        chat_id, 'কোন ধরনের নোটিশ পাঠাতে চান?', reply_markup=mk
    )


def process_exam_setup(message):
  try:
    parts = [p.strip() for p in message.text.split(',')]
    roll = int(parts[0])
    subject = parts[1]
    date_str = parts[2]
    time_str = parts[3]

    exam_datetime = datetime.datetime.strptime(
        f'{date_str} {time_str}', '%d-%m-%Y %I:%M %p'
    )

    updated = False
    for uid, data in users_db.items():
      if data.get('roll') == roll:
        users_db[uid]['exam_sub'] = subject
        users_db[uid]['exam_date'] = date_str
        users_db[uid]['exam_time'] = time_str
        users_db[uid]['exam_dt'] = exam_datetime
        updated = True

        lang = users_db[uid].get('lang', 'bn')
        bot.send_message(
            uid,
            f'🔔 *New Exam Schedule Added!*\n\n{subject} exam on {date_str} at'
            f' {time_str}',
            parse_mode='Markdown',
        )
        break

    if updated:
      bot.send_message(
          message.chat.id, '✅ এক্সাম শিডিউল সফলভাবে সেট করা হয়েছে!'
      )
    else:
      bot.send_message(
          message.chat.id, '❌ এই রোল নম্বরের কাউকে পাওয়া যায়নি।'
      )

  except Exception:
    bot.send_message(
        message.chat.id,
        '❌ ফরমেট ভুল হয়েছে। দয়া করে আবার চেষ্টা করুন।',
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith('notice_'))
def ask_notice_text(call):
  chat_id = call.message.chat.id
  n_type = (
      '🥳 *অভিনন্দন!*\n\n'
      if call.data == 'notice_congrats'
      else '📢 *জরুরী নোটিশ!*\n\n'
  )

  msg = bot.send_message(
      chat_id, 'নোটিশের লেখাটি (Text) বা ছবিসহ ক্যাপশন পাঠিয়ে দিন:'
  )
  bot.register_next_step_handler(msg, send_notice_to_all, n_type)


def send_notice_to_all(message, notice_type):
  success_count = 0
  for uid, data in users_db.items():
    if data.get('is_approved'):
      try:
        if message.content_type == 'text':
          bot.send_message(
              uid, f'{notice_type}{message.text}', parse_mode='Markdown'
          )
        elif message.content_type == 'photo':
          bot.send_photo(
              uid,
              message.photo[-1].file_id,
              caption=f'{notice_type}{message.caption or ""}',
              parse_mode='Markdown',
          )
        success_count += 1
      except Exception:
        pass

  bot.send_message(
      message.chat.id,
      f'✅ নোটিশটি সফলভাবে {success_count} জন ইউজারের কাছে পাঠানো'
      ' হয়েছে।',
  )


# ==========================================
# 9. EXAM ALERTS THREAD
# ==========================================
def exam_alert_thread():
  while True:
    now = datetime.datetime.now()
    for uid, data in users_db.items():
      if data.get('exam_dt'):
        dt = data['exam_dt']
        diff = (dt - now).total_seconds()
        if 3540 <= diff <= 3600:  # Exactly 1 hour before
          bot.send_message(
              uid,
              '⚠️ *Reminder:* Your exam starts in 1 hour!',
              parse_mode='Markdown',
          )
          data['exam_dt'] = None  # prevent duplicate alerts
    time.sleep(60)


# ==========================================
# RUN BOT
# ==========================================
if __name__ == '__main__':
  t1 = threading.Thread(target=run_web_server)
  t1.daemon = True
  t1.start()

  t2 = threading.Thread(target=exam_alert_thread)
  t2.daemon = True
  t2.start()

  print('Bot is running smoothly...')
  bot.infinity_polling()
