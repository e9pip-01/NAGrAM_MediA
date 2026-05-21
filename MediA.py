import os
import asyncio
import glob
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReactionTypeEmoji, InputMediaDocument
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

async def send_animated_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_to_id: int):
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
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
            
        chunks = []
        skip = False
        for i in range(len(words)):
            if skip:
                skip = False
                continue
            
            current_w = words[i]
            if 'ء' in current_w or current_w.strip() == 'ء':
                chunks.append(current_w)
            else:
                if i + 1 < len(words):
                    next_w = words[i+1]
                    if 'ء' in next_w or next_w.strip() == 'ء':
                        chunks.append(current_w)
                    else:
                        chunks.append(current_w + next_w)
                        skip = True
                else:
                    chunks.append(current_w)
                    
        for c_idx, chunk in enumerate(chunks):
            if not chunk.strip() and c_idx == 0 and len(chunks) == 1:
                continue
            
            if current_display == "":
                current_display = chunk
            else:
                if c_idx == 0 and l_idx > 0:
                    current_display += "\n" + chunk
                else:
                    current_display += chunk
            
            if msg is None:
                msg = await update.message.reply_text(current_display, reply_to_message_id=reply_to_id)
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
    bot_msg = await send_animated_text(update, context, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await update.message.reply_text("👅")
    if bot_msg:
        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot_msg = await send_animated_text(update, context, "هلا مولاي زبك يالون ههع يلا راح امص\nعقءعقءعقء اهعاعقءعقءعاهعقء", user_msg_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("👅")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(executor, get_media_info, url)
    except Exception:
        bot_msg = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("🫧")
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
        return

    msg3 = await send_animated_text(update, context, "دانفذ طلبك انتظر مولاي\nبليز", user_msg_id)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
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
            'outtmpl': 'downloads/%(uploader,channel_id,channel)s - %(title,id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'restrictfilenames': True,
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
            
            if media_group:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_msgs[0].message_id if sent_msgs else None
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
                
            await delete_waiting_messages()

            for f in opened_files:
                f.close()
            for f in files_to_remove:
                if os.path.exists(f):
                    os.remove(f)
            return
        except Exception:
            bot_msg = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await update.message.reply_text("🫧")
            await delete_waiting_messages()
            if bot_msg:
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
            return

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(uploader,channel_id,channel)s - %(title,id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
        'restrictfilenames': True,
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
                bot_msg = await send_animated_text(update, context, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            mime_type, _ = mimetypes.guess_type(real_filename)
            if mime_type:
                if mime_type.startswith('video/'):
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
                elif mime_type.startswith('image/'):
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
                elif mime_type.startswith('audio/'):
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_AUDIO)
                else:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
            else:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
                
            with open(real_filename, 'rb') as document:
                sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_doc.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            await delete_waiting_messages()
            os.remove(real_filename)
            
    except yt_dlp.utils.MaxFileSizeReached:
        bot_msg = await send_animated_text(update, context, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("🧸")
        await delete_waiting_messages()
        if bot_msg:
            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
    except Exception:
        bot_msg = await send_animated_text(update, context, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        await update.message.reply_text("🫧")
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
    
    app.run_polling()

if __name__ == '__main__':
    main()