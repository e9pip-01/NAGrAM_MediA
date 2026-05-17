import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, ReactionTypeEmoji
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

TOKEN = "8775972336:AAGAPoxZd0LdKXtSHO2ADbu_evDWYTlMA2M"
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

async def remove_audio_ffmpeg(input_path, output_path):
    cmd = f'ffmpeg -y -i "{input_path}" -an -c:v copy "{output_path}"'
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()

async def send_animated_text(update: Update, text: str, reply_to_id: int):
    lines = text.split('\n')
    current_display = ""
    msg = None
    
    for l_idx, line in enumerate(lines):
        words = line.split(' ')
        for w_idx, word in enumerate(words):
            if not word and w_idx == 0 and len(words) == 1:
                continue
            
            if current_display == "":
                current_display = word
            else:
                if w_idx == 0 and l_idx > 0:
                    current_display += "\n" + word
                else:
                    current_display += " " + word
            
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
    bot_msg = await send_animated_text(update, "هلا بيك دز رابط الميديا\nالتريدها", user_msg_id)
    await update.message.reply_text("⏳")
    if bot_msg:
        asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_msg_id = update.message.message_id
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot_msg = await send_animated_text(update, "هلا بيك دز رابط الميديا\nالتريدها", user_msg_id)
        await update.message.reply_text("⏳")
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
            'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s_%(index)s.%(ext)s',
            'max_filesize': MAX_SIZE_BYTES,
            'restrictfilenames': True,
        }
        try:
            download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
                
            from telegram import InputMediaDocument
            media_group = []
            files_to_remove = []
            
            for entry in download_info.get('entries', []):
                if not entry:
                    continue
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    file_path = ydl.prepare_filename(entry)
                if os.path.exists(file_path):
                    files_to_remove.append(file_path)
                    media_group.append(InputMediaDocument(open(file_path, 'rb')))
            
            if media_group:
                sent_msgs = await update.message.reply_media_group(media=media_group, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_msgs[0].message_id if sent_msgs else None
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
                
                for f_path, s_msg in zip(files_to_remove, sent_msgs):
                    if f_path.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
                        dir_name = os.path.dirname(f_path)
                        base_name = os.path.basename(f_path)
                        animation_path = os.path.join(dir_name, "mute_" + base_name)
                        try:
                            await remove_audio_ffmpeg(f_path, animation_path)
                            if os.path.exists(animation_path) and os.path.getsize(animation_path) > 0:
                                with open(animation_path, 'rb') as anim_file:
                                    await update.message.reply_animation(animation=anim_file, reply_to_message_id=s_msg.message_id)
                        except Exception:
                            pass
                        finally:
                            if os.path.exists(animation_path):
                                os.remove(animation_path)
                
            await delete_waiting_messages()

            for f in files_to_remove:
                if os.path.exists(f):
                    os.remove(f)
            return
        except Exception:
            bot_msg = await send_animated_text(update, "الرابط غير مدعوم او الموقع\nغير مدعوم", user_msg_id)
            await update.message.reply_text("🫧")
            await delete_waiting_messages()
            if bot_msg:
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
            return

    ydl_opts = {
        'outtmpl': 'downloads/%(uploader,channel)s - %(title,id)s.%(ext)s',
        'max_filesize': MAX_SIZE_BYTES,
        'restrictfilenames': True,
    }
    
    try:
        loop = asyncio.get_event_loop()
        download_info = await loop.run_in_executor(executor, download_media, ydl_opts, url)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            filename = ydl.prepare_filename(download_info)
            
        if not os.path.exists(filename):
            ext = download_info.get('ext', 'mp4')
            filename = os.path.splitext(filename)[0] + f".{ext}"

        if os.path.exists(filename):
            if os.path.getsize(filename) > MAX_SIZE_BYTES:
                os.remove(filename)
                bot_msg = await send_animated_text(update, "ماكدر اشيل عير اطول من كسي\nالعفو منك مولاي", user_msg_id)
                await update.message.reply_text("🧸")
                await delete_waiting_messages()
                if bot_msg:
                    asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg.message_id))
                return
            
            with open(filename, 'rb') as document:
                sent_doc = await update.message.reply_document(document=document, reply_to_message_id=user_msg_id)
                bot_msg_id = sent_doc.message_id
                asyncio.create_task(add_strawberry_reactions(context, chat_id, user_msg_id, bot_msg_id))
            
            await delete_waiting_messages()
            
            if filename.lower().endswith(('.mp4', '.mkv', '.webm', '.mov', '.avi')):
                dir_name = os.path.dirname(filename)
                base_name = os.path.basename(filename)
                animation_path = os.path.join(dir_name, "mute_" + base_name)
                try:
                    await remove_audio_ffmpeg(filename, animation_path)
                    if os.path.exists(animation_path) and os.path.getsize(animation_path) > 0:
                        with open(animation_path, 'rb') as anim_file:
                            await update.message.reply_animation(animation=anim_file, reply_to_message_id=bot_msg_id)
                except Exception:
                    pass
                finally:
                    if os.path.exists(animation_path):
                        os.remove(animation_path)

            if os.path.exists(filename):
                os.remove(filename)
            
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
        
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()