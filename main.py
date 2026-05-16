import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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

async def send_media_details(update_or_query, info):
    channel = info.get('uploader') or info.get('channel') or "Unknown Channel"
    title = info.get('title') or info.get('id') or "No Title/ID"
    details_text = f"{channel}\n{title}"
    if isinstance(update_or_query, Update):
        await update_or_query.message.reply_text(details_text)
    else:
        await update_or_query.message.reply_text(details_text)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("هلا بيك دز رابط الميديا\nالتريدها")
    await update.message.reply_text("⚽")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("هلا بيك دز رابط الميديا\nالتريدها")
        await update.message.reply_text("⚽")
        return

    await update.message.reply_text("كاعدة اطلع الك معلومات الميديا\nالتريدها")
    await update.message.reply_text("⏳")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, get_media_info, url)
    except Exception:
        await update.message.reply_text("الرابط غير مدعوم او الموقع\nغير مدعوم")
        await update.message.reply_text("🫧")
        return

    if 'entries' in info and not info.get('formats'):
        await send_media_details(update, info)
        await update.message.reply_text("دانفذ طلبك انتظر مولاي\nبليز")
        await update.message.reply_text("🫦")
        
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
                await update.message.reply_media_group(media=media_group)
                
            for f in files_to_remove:
                if os.path.exists(f):
                    os.remove(f)
            return
        except Exception:
            await update.message.reply_text("الرابط غير مدعوم او الموقع\nغير مدعوم")
            await update.message.reply_text("🫧")
            return

    formats = info.get('formats', [])
    available_formats = []
    seen_resolutions = set()

    for f in formats:
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
            res = f.get('height')
            if res and res not in seen_resolutions:
                seen_resolutions.add(res)
                available_formats.append(f)

    available_formats = sorted(available_formats, key=lambda x: x.get('height', 0), reverse=True)
    context.user_data[url] = {'type': 'single', 'info': info, 'formats': available_formats}

    keyboard = []
    for f in available_formats:
        res_name = f"{f.get('height')}p"
        keyboard.append([InlineKeyboardButton(res_name, callback_data=f"format|{f['format_id']}|{url}")])
    
    keyboard.append([InlineKeyboardButton("صوت MP3", callback_data=f"audio|{url}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text="", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('|')
    action = data[0]
    url = data[-1]
    
    stored = context.user_data.get(url)
    if stored and 'info' in stored:
        await send_media_details(query, stored['info'])
        
    await query.message.reply_text("دانفذ طلبك انتظر مولاي\nبليز")
    await query.message.reply_text("🫦")

    if action == "format":
        format_id = data[1]
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
        }
        
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
                
            if os.path.exists(filename):
                if os.path.getsize(filename) > MAX_SIZE_BYTES:
                    os.remove(filename)
                    await query.message.reply_text("ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي")
                    await query.message.reply_text("🧸")
                    return
                
                with open(filename, 'rb') as video:
                    await query.message.reply_video(video=video, supports_streaming=True)
                os.remove(filename)
        except yt_dlp.utils.MaxFileSizeReached:
            await query.message.reply_text("ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي")
            await query.message.reply_text("🧸")
        except Exception:
            await query.message.reply_text("الرابط غير مدعوم او الموقع\nغير مدعوم")
            await query.message.reply_text("🫧")

    elif action == "audio":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': MAX_SIZE_BYTES,
        }
        try:
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
                filename = ydl.prepare_filename(info)
                audio_filename = os.path.splitext(filename)[0] + ".mp3"
                
            if os.path.exists(audio_filename):
                if os.path.getsize(audio_filename) > MAX_SIZE_BYTES:
                    os.remove(audio_filename)
                    await query.message.reply_text("ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي")
                    await query.message.reply_text("🧸")
                    return
                
                with open(audio_filename, 'rb') as audio:
                    await query.message.reply_audio(audio=audio)
                os.remove(audio_filename)
        except Exception:
            await query.message.reply_text("الرابط غير مدعوم او الموقع\nغير مدعوم")
            await query.message.reply_text("🫧")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
