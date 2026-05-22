import os
import asyncio
import glob
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReactionTypeEmoji
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
            'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'restrictfilenames': True,
        }
        try:
            download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
            await delete_waiting_messages()
            
            for entry in download_info.get('entries', []):
                if not entry:
                    continue
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    file_path = ydl.prepare_filename(entry)
                
                base_name = os.path.splitext(file_path)[0]
                matching_files = glob.glob(f"{base_name}.*")
                
                if matching_files:
                    real_file_path = matching_files[0]
                    
                    if os.path.getsize(real_file_path) > MAX_SIZE_BYTES:
                        if os.path.exists(real_file_path):
                            os.remove(real_file_path)
                        continue
                    
                    try:
                        with open(real_file_path, 'rb') as document:
                            sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                            asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, sent_doc.message_id))
                    except Exception:
                        pass
                    finally:
                        if os.path.exists(real_file_path):
                            os.remove(real_file_path)
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
        'outtmpl': 'downloads/%%(uploader,channel)s - %(title,id)s.%(ext)s',
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
                bot_msg = await send_animated_text(update, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            with open(real_filename, 'rb') as document:
                sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_doc.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            await delete_waiting_messages()
            os.remove(real_filename)
            
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