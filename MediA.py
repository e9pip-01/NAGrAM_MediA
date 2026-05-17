import os
import asyncio
import sqlite3
import re
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
import yt_dlp

TOKEN = "8775972336:AAGAPoxZd0LdKXtSHO2ADbu_evDWYTlMA2M"
MAX_SIZE_BYTES = 567 * 1024 * 1024
DB_NAME = "replies.db"

BTN_ADD_SINGLE = "اضف رد"
BTN_DEL_SINGLE = "مسح رد"
BTN_ADD_MULTI = "اضف رد متعدد"
BTN_DEL_MULTI = "مسح رد متعدد"
BTN_FINISH = "اضغط هنا لإنهاء الإضافه"
BTN_TOTAL = "كلي"
BTN_SINGLE = "فردي"
BTN_LOOP = "مستمر"
BTN_CANCEL = "الغاء"

TXT_MAIN_MENU = "مرحباً بك في لوحة تحكم البوت ⚙️"
TXT_REQ_KEYWORD = "— ارسل الان الكلمة لاضافتها في الردود ."
TXT_REQ_REPLY = "— قم بارسال الرد الذي تريد اضافه ."
TXT_SAVE_SUCCESS = "— تم حفظ الردود بنجاح .\n— قم بتحديد نوع الارسال (فردي، كلي، مستمر) ."
TXT_PROCESS = "دانفذ طلبك انتظر مولاي\nبليز"
TXT_ERROR_LINK = "الرابط غير مدعوم او الموقع\nغير مدعوم"
TXT_SIZE_EXCEED = "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي"
TXT_CANCELLED = "تم الإلغاء ."

CHOOSE_KEYWORD, CHOOSE_REPLIES, CHOOSE_TYPE = range(3)
active_loops = {}
executor = ThreadPoolExecutor(max_workers=20)

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reply_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            type TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reply_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            file_id TEXT,
            text TEXT,
            media_type TEXT,
            FOREIGN KEY (word_id) REFERENCES reply_words(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_counters (
            chat_id INTEGER,
            word_id INTEGER,
            current_index INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, word_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def clean_filename(title):
    title = re.sub(r'[\\/*?:"<>|#\s]+', ' ', title)
    return title.strip()

def get_media_info(url):
    ydl_opts = {'extract_flat': False, 'skip_download': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_media(ydl_opts, url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)

async def remove_audio_ffmpeg(input_path, output_path):
    cmd = f'ffmpeg -y -i "{input_path}" -an -c:v copy "{output_path}"'
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()

async def send_animated_text(update: Update, text: str, reply_to_id: int):
    parts = text.split('ء')
    current_display = ""
    msg = None
    
    for idx, part in enumerate(parts):
        if not part.strip() and idx == len(parts) - 1:
            continue
            
        if current_display == "":
            current_display = part
        else:
            current_display += part
            
        if msg is None:
            if update.message:
                msg = await update.message.reply_text(current_display, reply_to_message_id=reply_to_id)
            elif update.callback_query:
                msg = await update.callback_query.message.reply_text(current_display, reply_to_message_id=reply_to_id)
        else:
            await asyncio.sleep(0.1)
            try:
                await msg.edit_text(current_display)
            except Exception:
                pass
    return msg

async def add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id):
    await asyncio.sleep(3)
    for msg_id in [user_msg_id, bot_msg_id]:
        if msg_id:
            try:
                await context.bot.set_message_reaction(
                    chat_id=chat_id, message_id=msg_id, reaction=[ReactionTypeEmoji(emoji="🍓")]
                )
            except Exception:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    bot_msg = await send_animated_text(update, "هلا بيك دز رابط الميدياءالتريدها", user_msg_id)
    await update.message.reply_text("⏳")
    if bot_msg:
        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(BTN_ADD_SINGLE, callback_data="add_single"), InlineKeyboardButton(BTN_DEL_SINGLE, callback_data="del_single")],
        [InlineKeyboardButton(BTN_ADD_MULTI, callback_data="add_multi"), InlineKeyboardButton(BTN_DEL_MULTI, callback_data="del_multi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(TXT_MAIN_MENU, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(TXT_MAIN_MENU, reply_markup=reply_markup)

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(TXT_CANCELLED)
    else:
        await update.message.reply_text(TXT_CANCELLED)
    context.user_data.clear()
    return ConversationHandler.END

async def add_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['multi'] = (query.data == "add_multi")
    keyboard = [[InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_conv")]]
    await query.edit_message_text(TXT_REQ_KEYWORD, reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_KEYWORD

async def add_reply_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    context.user_data['keyword'] = keyword
    context.user_data['replies'] = []
    
    keyboard = [[InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_conv")]]
    await update.message.reply_text(TXT_REQ_REPLY, reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_REPLIES

async def add_reply_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    reply_item = {}
    
    if msg.text:
        reply_item = {'type': 'text', 'data': msg.text}
    elif msg.photo:
        reply_item = {'type': 'photo', 'data': msg.photo[-1].file_id}
    elif msg.animation:
        reply_item = {'type': 'animation', 'data': msg.animation.file_id}
    elif msg.video:
        reply_item = {'type': 'video', 'data': msg.video.file_id}
    elif msg.document:
        reply_item = {'type': 'document', 'data': msg.document.file_id}
        
    if reply_item:
        context.user_data['replies'].append(reply_item)
        
    if not context.user_data.get('multi', False):
        return await show_type_selection(update, context)
    else:
        keyboard = [
            [InlineKeyboardButton(BTN_FINISH, callback_data="finish_multi")],
            [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_conv")]
        ]
        await update.message.reply_text("— تم حفظ الرد يمكنك ارسال اخر او اكمال العمليه من خلال الزر اسفل √.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSE_REPLIES

async def finish_multi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await show_type_selection(query, context)

async def show_type_selection(update_or_query, context):
    keyboard = [
        [InlineKeyboardButton(BTN_TOTAL, callback_data="type_total"), InlineKeyboardButton(BTN_SINGLE, callback_data="type_single")],
        [InlineKeyboardButton(BTN_LOOP, callback_data="type_loop")],
        [InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_conv")]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    if isinstance(update_or_query, Update) and update_or_query.message:
        await update_or_query.message.reply_text(TXT_SAVE_SUCCESS, reply_markup=markup)
    else:
        await update_or_query.message.reply_text(TXT_SAVE_SUCCESS, reply_markup=markup)
    return CHOOSE_TYPE

async def save_reply_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    mode_map = {"type_total": "total", "type_single": "single", "type_loop": "loop"}
    selected_mode = mode_map.get(query.data, "total")
    
    keyword = context.user_data.get('keyword')
    replies = context.user_data.get('replies', [])
    
    if not keyword or not replies:
        await query.edit_message_text("خطأ في البيانات.")
        return ConversationHandler.END
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM reply_words WHERE keyword = ?", (keyword,))
        cursor.execute("INSERT INTO reply_words (keyword, type) VALUES (?, ?)", (keyword, selected_mode))
        word_id = cursor.lastrowid
        for r in replies:
            if r['type'] == 'text':
                cursor.execute("INSERT INTO reply_contents (word_id, text, media_type) VALUES (?, ?, ?)", (word_id, r['data'], 'text'))
            else:
                cursor.execute("INSERT INTO reply_contents (word_id, file_id, media_type) VALUES (?, ?, ?)", (word_id, r['data'], r['type']))
        conn.commit()
        await query.edit_message_text("— تم التعيين بنجاح .")
    except Exception as e:
        await query.edit_message_text(f"حدث خطأ: {e}")
    finally:
        conn.close()
        
    context.user_data.clear()
    return ConversationHandler.END

async def delete_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_multi = (query.data == "del_multi")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if is_multi:
        cursor.execute("SELECT keyword FROM reply_words WHERE type IN ('total', 'single', 'loop')")
    else:
        cursor.execute("SELECT keyword FROM reply_words")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await query.edit_message_text("لا توجد ردود مسجلة حالياً.")
        return
        
    keyboard = []
    for row in rows:
        keyboard.append([InlineKeyboardButton(row[0], callback_data=f"delkw_{row[0]}")])
    keyboard.append([InlineKeyboardButton(BTN_CANCEL, callback_data="cancel_control")])
    
    await query.edit_message_text("اختر الكلمة التي تريد حذفها:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyword = query.data.split('_', 1)[1]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reply_words WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text(f"تم حذف الرد الخاص بـ '{keyword}' بنجاح.")

async def cancel_control(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("تم إغلاق لوحة التحكم.")

async def handle_loop_reply(update, context, rows):
    chat_id = update.effective_chat.id
    if chat_id in active_loops:
        active_loops[chat_id] = False
        await asyncio.sleep(0.5)
    
    active_loops[chat_id] = True
    user_msg_id = update.message.message_id
    
    try:
        while active_loops.get(chat_id, False):
            for row in rows:
                if not active_loops.get(chat_id, False):
                    break
                file_id, text, media_type = row
                await send_db_media(update, context, file_id, text, media_type, user_msg_id)
                await asyncio.sleep(2)
    except Exception:
        pass

async def send_db_media(update, context, file_id, text, media_type, reply_id):
    try:
        if media_type == 'text':
            if 'ء' in text:
                await send_animated_text(update, text, reply_id)
            else:
                await update.message.reply_text(text, reply_to_message_id=reply_id)
        elif media_type == 'photo':
            await update.message.reply_photo(photo=file_id, reply_to_message_id=reply_id)
        elif media_type == 'animation':
            await update.message.reply_animation(animation=file_id, reply_to_message_id=reply_id)
        elif media_type == 'video':
            await update.message.reply_video(video=file_id, reply_to_message_id=reply_id)
        elif media_type == 'document':
            await update.message.reply_document(document=file_id, reply_to_message_id=reply_id)
    except Exception:
        pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip() if update.message.text else ""
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if chat_id in active_loops:
        active_loops[chat_id] = False

    if text and not (text.startswith("http://") or text.startswith("https://")):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, type FROM reply_words WHERE keyword = ?", (text,))
        word_row = cursor.fetchone()
        
        if word_row:
            word_id, mode = word_row
            cursor.execute("SELECT file_id, text, media_type FROM reply_contents WHERE word_id = ? ORDER BY id ASC", (word_id,))
            rows = cursor.fetchall()
            
            if rows:
                if mode == 'total':
                    for row in rows:
                        file_id, r_text, media_type = row
                        await send_db_media(update, context, file_id, r_text, media_type, user_msg_id)
                elif mode == 'single':
                    cursor.execute("SELECT current_index FROM word_counters WHERE chat_id = ? AND word_id = ?", (chat_id, word_id))
                    idx_row = cursor.fetchone()
                    current_idx = idx_row[0] if idx_row else 0
                    if current_idx >= len(rows):
                        current_idx = 0
                        
                    file_id, r_text, media_type = rows[current_idx]
                    await send_db_media(update, context, file_id, r_text, media_type, user_msg_id)
                    
                    next_idx = current_idx + 1
                    cursor.execute("INSERT OR REPLACE INTO word_counters (chat_id, word_id, current_index) VALUES (?, ?, ?)",
                                   (chat_id, word_id, next_idx))
                    conn.commit()
                elif mode == 'loop':
                    asyncio.create_task(handle_loop_reply(update, context, rows))
                    
            conn.close()
            return
        conn.close()

    if not (text.startswith("http://") or text.startswith("https://")):
        bot_msg = await send_animated_text(update, "هلا بيك دز رابط الميدياءالتريدها", user_msg_id)
        await update.message.reply_text("⏳")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_media_info, text)
    except Exception:
        bot_msg = await send_animated_text(update, TXT_ERROR_LINK, user_msg_id)
        await update.message.reply_text("🫧")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    msg3 = await send_animated_text(update, TXT_PROCESS, user_msg_id)
    msg4 = await update.message.reply_text("🫦")

    async def delete_waiting_messages():
        for m in [msg3, msg4]:
            try:
                await m.delete()
            except Exception:
                pass

    ydl_opts = {
        'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
        'restrictfilenames': False,
    }
    
    try:
        download_info = await loop.run_in_executor(executor, download_media, ydl_opts, text)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            filename = ydl.prepare_filename(download_info)
            
        if not os.path.exists(filename):
            ext = download_info.get('ext', 'mp4')
            filename = os.path.splitext(filename)[0] + f".{ext}"

        if os.path.exists(filename):
            if os.path.getsize(filename) > MAX_SIZE_BYTES:
                os.remove(filename)
                bot_msg = await send_animated_text(update, TXT_SIZE_EXCEED, user_msg_id)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            dir_name = os.path.dirname(filename)
            base_name = os.path.basename(filename)
            name_part, ext_part = os.path.splitext(base_name)
            
            clean_base = clean_filename(name_part) + ext_part
            clean_path = os.path.join(dir_name, clean_base)
            os.rename(filename, clean_path)
            
            with open(clean_path, 'rb') as document:
                sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_doc.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            if clean_base.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
                animation_path = os.path.join(dir_name, "mute_" + clean_base)
                try:
                    await remove_audio_ffmpeg(clean_path, animation_path)
                    if os.path.exists(animation_path) and os.path.getsize(animation_path) > 0:
                        with open(animation_path, 'rb') as anim_file:
                            await update.message.reply_animation(animation=anim_file, reply_to_message_id=bot_msg_id)
                except Exception:
                    pass
                finally:
                    if os.path.exists(animation_path):
                        os.remove(animation_path)

            await delete_waiting_messages()
            if os.path.exists(clean_path):
                os.remove(clean_path)
            
    except Exception:
        bot_msg = await send_animated_text(update, TXT_ERROR_LINK, user_msg_id)
        await update.message.reply_text("🫧")
        await delete_waiting_messages()
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_reply_start, pattern="^(add_single|add_multi)$"),
            CommandHandler("add", add_reply_start)
        ],
        states={
            CHOOSE_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_reply_keyword)],
            CHOOSE_REPLIES: [
                CallbackQueryHandler(finish_multi_handler, pattern="^finish_multi$"),
                MessageHandler(filters.TEXT | filters.PHOTO | filters.ANIMATION | filters.VIDEO | filters.Document.ALL, add_reply_content)
            ],
            CHOOSE_TYPE: [CallbackQueryHandler(save_reply_final, pattern="^type_(total|single|loop)$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_handler, pattern="^cancel_conv$")],
        per_message=False
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("control", control_panel))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(delete_reply_start, pattern="^(del_single|del_multi)$"))
    app.add_handler(CallbackQueryHandler(delete_reply_button, pattern="^delkw_"))
    app.add_handler(CallbackQueryHandler(cancel_control, pattern="^cancel_control$"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()
