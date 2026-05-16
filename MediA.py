import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "8775972336:AAGAPoxZd0LdKXtSHO2ADbu_evDWYTlMA2M"
MAX_SIZE_BYTES = 567 * 1024 * 1024

def get_media_info(url):
    ydl_opts = {
        'extract_flat': False,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

async def send_animated_text(update: Update, text: str, reply_to_id: int):
    words = text.split()
    if not words:
        return None
    
    current_text = words[0]
    msg = await update.message.reply_text(current_text, reply_to_message_id=reply_to_id)
    
    for word in words[1:]:
        await asyncio.sleep(0.3)
        current_text += " " + word
        try:
            await msg.edit_text(current_text)
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
                    reaction=[{"type": "emoji", "emoji": "🍓"}]
                )
            except Exception:
                pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_animated_text(update, "هلا بيك دز رابط الميديا التريدها", update.message.message_id)
    await update.message.reply_text("⚽")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await send_animated_text(update, "هلا بيك دز رابط الميديا التريدها", user_msg_id)
        await update.message.reply_text("⚽")
        return

    msg1 = await send_animated_text(update, "كاعدة اطلع الك معلومات الميديا التريدها", user_msg_id)
    msg2 = await update.message.reply_text("⏳")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, get_media_info, url)
    except Exception:
        await send_animated_text(update, "الرابط غير مدعوم او الموقع غير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
        try:
            await msg1.delete()
            await msg2.delete()
        except Exception:
            pass
        return

    msg3 = await send_animated_text(update, "دانفذ طلبك انتظر مولاي بليز", user_msg_id)
    msg4 = await update.message.reply_text("🫦")

    async def delete_waiting_messages():
        for m in [msg1, msg2, msg3, msg4]:
            try:
                await m.delete()
            except Exception:
                pass

    if 'entries' in info and not info.get('formats'):
        ydl_opts = {
            'outtmpl': 'downloads/%(id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                download_info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                
            from telegram import InputMediaPhoto, InputMediaVideo
            media_group = []
            files_to_remove = []
            
            for entry in download_info.get('entries', []):
                if not entry:
                    continue
                file_path = ydl.prepare_filename(entry)
                if os.path.exists(file_path):
                    files_to_remove.append(file_path)
                    if entry.get('ext') in ['jpg', 'jpeg', 'png', 'webp']:
                        media_group.append(InputMediaPhoto(open(file_path, 'rb')))
                    else:
                        media_group.append(InputMediaVideo(open(file_path, 'rb')))
            
            if media_group:
                sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_msgs[0].message_id if sent_msgs else None
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
                
            await delete_waiting_messages()

            for f in files_to_remove:
                if os.path.exists(f):
                    os.remove(f)
            return
        except Exception:
            await send_animated_text(update, "الرابط غير مدعوم او الموقع غير مدعوم", user_msg_id)
            await update.message.reply_text("🫧")
            await delete_waiting_messages()
            return

    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            download_info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
            filename = ydl.prepare_filename(download_info)
            
            if not os.path.exists(filename):
                ext = download_info.get('ext', 'mp4')
                filename = os.path.splitext(filename)[0] + f".{ext}"

        if os.path.exists(filename):
            if os.path.getsize(filename) > MAX_SIZE_BYTES:
                os.remove(filename)
                await send_animated_text(update, "ماكدر اشيل عير اطول من كسي العفو منك مولاي", user_msg_id)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                return
            
            with open(filename, 'rb') as video:
                sent_video = await update.message.reply_video(video=video, supports_streaming=True, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_video.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            await delete_waiting_messages()
            os.remove(filename)
            
    except yt_dlp.utils.MaxFileSizeReached:
        await send_animated_text(update, "ماكدر اشيل عير اطول من كسي العفو منك مولاي", user_msg_id)
        await update.message.reply_text("🧸")
        await delete_waiting_messages()
    except Exception:
        await send_animated_text(update, "الرابط غير مدعوم او الموقع غير مدعوم", user_msg_id)
        await update.message.reply_text("🫧")
        await delete_waiting_messages()

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()