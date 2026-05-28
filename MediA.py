import os
import asyncio
import glob
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReactionTypeEmoji, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaVideo, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE_BYTES = 567 * 1024 * 1024

executor = ThreadPoolExecutor(max_workers=20)

def get_media_info(url):
    ydl_opts = {
        'extract_flat': False,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def download_media(ydl_opts, url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=True)

def get_video_dimensions(file_path):
    try:
        cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json "{file_path}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        if 'streams' in data and len(data['streams']) > 0:
            return data['streams'][0].get('width'), data['streams'][0].get('height')
    except Exception:
        pass
    return None, None

async def send_animated_text(update: Update, text: str, reply_to_id: int):
    lines = text.split('\n')
    current_display = ""
    msg = None
    
    for l_idx, line in enumerate(lines):
        words = []
        current_word = ""
        for char in line:
            current_word += char
            if char == ' ' or char == 'ء':
                words.append(current_word)
                current_word = ""
        if current_word:
            words.append(current_word)
            
        paired_words = []
        temp_pair = ""
        for w_idx, word in enumerate(words):
            temp_pair += word
            if (w_idx + 1) % 2 == 0 or (w_idx + 1) == len(words):
                paired_words.append(temp_pair)
                temp_pair = ""
                
        for p_idx, pair in enumerate(paired_words):
            if not pair.strip() and p_idx == 0 and len(paired_words) == 1:
                continue
            
            if current_display == "":
                current_display = pair
            else:
                if p_idx == 0 and l_idx > 0:
                    current_display += "\n" + pair
                else:
                    current_display += pair
            
            if msg is None:
                if update.message:
                    msg = await update.message.reply_text(current_display, reply_to_message_id=reply_to_id)
                else:
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
                    chat_id=chat_id,
                    message_id=msg_id,
                    reaction=[ReactionTypeEmoji(emoji="🍓")]
                )
            except Exception:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    bot_msg = await send_animated_text(update, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
    await update.message.reply_text("👅")
    if bot_msg:
        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot_msg = await send_animated_text(update, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
        await update.message.reply_text("👅")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_media_info, url)
    except Exception:
        bot_msg = await send_animated_text(update, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    msg3 = await send_animated_text(update, "دانفذ طلبك انتظر مولاي\nبليز", user_msg_id)
    msg4 = await update.message.reply_text("🫦")

    async def delete_waiting_messages():
        for m in [msg3, msg4]:
            try:
                await m.delete()
            except Exception:
                pass

    if 'entries' in info and not info.get('formats'):
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': 'downloads/%(channel)s - %(id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'windowsfilenames': True,
            'trim_file_name': 100,
        }
        try:
            download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
            await delete_waiting_messages()
            
            media_group = []
            files_to_remove = []
            
            for entry in download_info.get('entries', []):
                if not entry:
                    continue
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    file_path = ydl.prepare_filename(entry)
                
                base_name = os.path.splitext(file_path)[0]
                matching_files = [f for f in glob.glob(f"{base_name}.*") if not f.endswith('.part') and not f.endswith('.ytdl')]
                
                if matching_files:
                    real_file_path = matching_files[0]
                    ext = os.path.splitext(real_file_path)[1].lower()
                    
                    if os.path.getsize(real_file_path) > MAX_SIZE_BYTES:
                        if os.path.exists(real_file_path):
                            os.remove(real_file_path)
                        continue
                    
                    f = open(real_file_path, 'rb')
                    if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
                        media_group.append(InputMediaPhoto(media=f))
                    else:
                        v_w, v_h = get_video_dimensions(real_file_path)
                        media_group.append(InputMediaVideo(media=f, width=v_w, height=v_h, has_spoiler=True))
                    files_to_remove.append((real_file_path, f))
            
            if media_group:
                try:
                    sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                    if sent_msgs:
                        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, sent_msgs[0].message_id))
                except Exception:
                    pass
                finally:
                    for path, f_obj in files_to_remove:
                        f_obj.close()
                        if os.path.exists(path):
                            os.remove(path)
            return
        except Exception:
            bot_msg = await send_animated_text(update, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
            await update.message.reply_text("🫧")
            await delete_waiting_messages()
            if bot_msg:
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
            return

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(channel)s - %(id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
        'windowsfilenames': True,
        'trim_file_name': 100,
    }
    
    try:
        loop = asyncio.get_event_loop()
        download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            filename = ydl.prepare_filename(download_info)
            
        base_name = os.path.splitext(filename)[0]
        matching_files = [f for f in glob.glob(f"{base_name}.*") if not f.endswith('.part') and not f.endswith('.ytdl')]

        if matching_files:
            real_filename = matching_files[0]
            ext = os.path.splitext(real_filename)[1].lower()

            if os.path.getsize(real_filename) > MAX_SIZE_BYTES:
                os.remove(real_filename)
                bot_msg = await send_animated_text(update, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            if ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']:
                with open(real_filename, 'rb') as photo:
                    sent_msg = await update.message.reply_photo(photo=photo, reply_to_message_id=user_msg_id)
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, sent_msg.message_id))
                os.remove(real_filename)
            else:
                keyboard = [[InlineKeyboardButton("ستيكر", callback_data=f"gif_{url}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                v_w, v_h = get_video_dimensions(real_filename)
                
                with open(real_filename, 'rb') as video:
                    sent_msg = await update.message.reply_video(video=video, width=v_w, height=v_h, reply_to_message_id=user_msg_id, reply_markup=reply_markup, has_spoiler=True)
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, sent_msg.message_id))
                os.remove(real_filename)
            
            await delete_waiting_messages()
            
    except yt_dlp.utils.MaxFileSizeReached:
        bot_msg = await send_animated_text(update, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
        await update.message.reply_text("🧸")
        await delete_waiting_messages()
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
    except Exception:
        bot_msg = await send_animated_text(update, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
        await delete_waiting_messages()
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    chat_id = update.effective_chat.id
    user_msg_id = query.message.reply_to_message.message_id if query.message.reply_to_message else query.message.message_id

    if data.startswith("gif_"):
        original_url = data[4:]
        
        msg3 = await send_animated_text(update, "دانفذ طلبك انتظر مولاي\nبليز", user_msg_id)
        msg4 = await query.message.reply_text("🫦")

        async def delete_waiting_messages():
            for m in [msg3, msg4]:
                try:
                    await m.delete()
                except Exception:
                    pass

        ydl_opts = {
            'format': 'bestvideo',
            'outtmpl': 'downloads/gif_%(channel)s - %(id)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'windowsfilenames': True,
            'trim_file_name': 100,
        }
        
        try:
            loop = asyncio.get_event_loop()
            download_info = await loop.run_in_executor(executor, download_media, ydl_opts, original_url)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                filename = ydl.prepare_filename(download_info)
                
            base_name = os.path.splitext(filename)[0]
            matching_files = [f for f in glob.glob(f"{base_name}.*") if not f.endswith('.part') and not f.endswith('.ytdl')]

            if matching_files:
                real_filename = matching_files[0]
                
                g_w, g_h = get_video_dimensions(real_filename)
                
                with open(real_filename, 'rb') as anim:
                    sent_anim = await query.message.reply_animation(animation=anim, width=g_w, height=g_h, reply_to_message_id=user_msg_id, has_spoiler=True)
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, sent_anim.message_id))
                
                os.remove(real_filename)
                await delete_waiting_messages()
        except Exception:
            bot_msg = await send_animated_text(update, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
            await query.message.reply_text("🫧")
            await delete_waiting_messages()
            if bot_msg:
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    if not TOKEN:
        return
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
