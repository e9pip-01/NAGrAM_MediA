import os
import asyncio
import glob
import re
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReactionTypeEmoji, InputMediaDocument, InputMediaPhoto
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN")
MAX_SIZE_BYTES = 567 * 1024 * 1024

executor = ThreadPoolExecutor(max_workers=20)

YDL_OPTIONS = {
    'extract_flat': False,
    'skip_download': True,
    'quiet': True,
    'no_warnings': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
}

def get_media_info(url):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        return ydl.extract_info(url, download=False)

def download_media(ydl_opts, url):
    opts = {**ydl_opts, **YDL_OPTIONS}
    opts['skip_download'] = False
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)

async def send_animated_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_to_id: int):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    lines = text.split('\n')
    current_display = ""
    msg = None
    emoji_msg = None
    
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
            
        for w_idx, word in enumerate(words):
            if not word.strip() and w_idx == 0 and len(words) == 1:
                continue
            
            if current_display == "":
                current_display = word
            else:
                if w_idx == 0 and l_idx > 0:
                    current_display += "\n" + word
                else:
                    current_display += word
            
            if msg is None:
                msg = await update.message.reply_text(current_display, reply_to_message_id=reply_to_id)
            else:
                await asyncio.sleep(0.1)
                try:
                    await msg.edit_text(current_display)
                except Exception:
                    pass
            
            if "بليز" in word and emoji_msg is None:
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                    emoji_msg = await update.message.reply_text("🫦")
                except Exception:
                    pass
                    
    return msg, emoji_msg

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
    bot_msg, _ = await send_animated_text(update, context, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
    await update.message.reply_text("👅")
    if bot_msg:
        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot_msg, _ = await send_animated_text(update, context, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
        await update.message.reply_text("👅")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_media_info, url)
    except Exception:
        bot_msg, _ = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    all_images = []
    if info:
        if 'requested_downloads' in info:
            all_images = [f.get('url') for f in info['requested_downloads'] if f.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] or 'image' in f.get('format_id', '')]
        
        if not all_images and 'entries' in info:
            for entry in info['entries']:
                if entry:
                    if entry.get('url') and (entry.get('ext') in ['jpg', 'jpeg', 'png', 'webp'] or 'image' in entry.get('format_id', '')):
                        all_images.append(entry['url'])
                    elif 'requested_downloads' in entry:
                        for f in entry['requested_downloads']:
                            if f.get('url'):
                                all_images.append(f['url'])

    if all_images:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
            media_group = [InputMediaPhoto(img_url) for img_url in all_images[:10]]
            if media_group:
                sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_msgs[0].message_id if sent_msgs else None
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            return
        except Exception:
            pass

    msg3, msg4 = await send_animated_text(update, context, "دانفذ طلبك انتظر مولاي\nبليز", user_msg_id)

    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT))
                )
            except Exception:
                pass

            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total:
                percent = (downloaded / total) * 100
                percent_str = f"{percent:.1f}%"
            else:
                percent_str = "جاري الحساب..."
            
            clean_str = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_percent_str', percent_str)).strip()
            
            if "100" in clean_str:
                new_text = "دانفذ طلبك انتظر مولاي\nبليز"
            else:
                new_text = f"دانفذ طلبك انتظر مولاي\nبليز - {clean_str}"
            
            try:
                coro = msg3.edit_text(new_text)
                asyncio.run_coroutine_threadsafe(coro, loop)
            except Exception:
                pass
        elif d['status'] == 'finished':
            try:
                coro = msg3.edit_text("دانفذ طلبك انتظر مولاي\nبليز")
                asyncio.run_coroutine_threadsafe(coro, loop)
            except Exception:
                pass

    if 'entries' in info and not info.get('formats'):
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'restrictfilenames': True,
            'progress_hooks': [progress_hook],
        }
        try:
            download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
                
            media_group = []
            opened_files = []
            files_to_remove = []
            
            for entry in download_info.get('entries', []):
                if not entry:
                    continue
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    file_path = ydl.prepare_filename(entry)
                
                base_name = os.path.splitext(file_path)[0]
                matching_files = glob.glob(f"{base_name}.*")
                
                if matching_files:
                    real_file_path = matching_files[0]
                    files_to_remove.append(real_file_path)
                    f = open(real_file_path, 'rb')
                    opened_files.append(f)
                    media_group.append(InputMediaDocument(f))
            
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

            if media_group:
                sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_msgs[0].message_id if sent_msgs else None
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
                
            for f in opened_files:
                f.close()
            for f in files_to_remove:
                if os.path.exists(f):
                    os.remove(f)
            return
        except Exception:
            bot_msg, _ = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
            await update.message.reply_text("🫧")
            if bot_msg:
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
            return

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
        'restrictfilenames': True,
        'progress_hooks': [progress_hook],
    }
    
    try:
        loop = asyncio.get_event_loop()
        download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            filename = ydl.prepare_filename(download_info)
            
        base_name = os.path.splitext(filename)[0]
        matching_files = glob.glob(f"{base_name}.*")

        if matching_files:
            real_filename = matching_files[0]

            if os.path.getsize(real_filename) > MAX_SIZE_BYTES:
                os.remove(real_filename)
                bot_msg, _ = await send_animated_text(update, context, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
                await update.message.reply_text("🧸")
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            with open(real_filename, 'rb') as document:
                sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_doc.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            os.remove(real_filename)
            
    except yt_dlp.utils.MaxFileSizeReached:
        bot_msg, _ = await send_animated_text(update, context, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
        await update.message.reply_text("🧸")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
    except Exception:
        bot_msg, _ = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
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
    
    app.run_polling()

if __name__ == '__main__':
    main()