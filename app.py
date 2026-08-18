import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web
import yt_dlp
from telethon import TelegramClient
import edge_tts
from pydub import AudioSegment

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Telethon Userbot mijozini sozlash
userbot = None
if API_ID and API_HASH:
    userbot = TelegramClient('userbot_session', int(API_ID), API_HASH)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Statistika ma'lumotlari
stats_data = {
    "sent_messages": 0,
    "checked_channels": 0,
    "downloaded_media": 0,
    "anonymous_chats": 0
}

async def handle_web(request):
    html_file_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(html_file_path):
        return web.FileResponse(html_file_path)
    return web.Response(text="index.html fayli topilmadi!", status=404)

# 1. DASHBOARD STATISTIKASI API
async def handle_get_stats(request):
    return web.json_response({
        "status": "success",
        "stats": stats_data
    })

# 2. ANONIM XABAR YUBORISH API
async def handle_send_anon(request):
    try:
        data = await request.json()
        target_id = data.get("target_id")
        text = data.get("message")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Anonim Javob Berish", callback_data="reply_anon")]
        ])

        await bot.send_message(
            chat_id=int(target_id),
            text=f"🎭 **Sizga anonim xabar keldi:**\n\n{text}",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        stats_data["sent_messages"] += 1
        stats_data["anonymous_chats"] += 1
        return web.json_response({"status": "success", "message": "Anonim xabar muvaffaqiyatli yuborildi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

# 3. FORWARDER / AUTO-POST API
async def handle_forward_posts(request):
    try:
        data = await request.json()
        from_chat = data.get("from_chat")
        to_chat = data.get("to_chat")
        limit = int(data.get("limit", 5))

        if not from_chat.startswith("@"): from_chat = f"@{from_chat}"
        if not to_chat.startswith("@"): to_chat = f"@{to_chat}"

        asyncio.create_task(run_forwarder(from_chat, to_chat, limit))
        return web.json_response({"status": "success", "message": f"{limit} ta post ko'chirish jarayoni boshlandi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

async def run_forwarder(from_chat, to_chat, limit):
    for i in range(limit):
        try:
            await asyncio.sleep(2)
        except Exception as e:
            logging.error(f"Forward xatosi: {e}")

# 4. MEDIA DOWNLOADER API (YT, Instagram, TikTok)
async def handle_download_media(request):
    try:
        data = await request.json()
        url = data.get("url")
        target_id = data.get("target_id")

        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloaded_media.%(ext)s',
            'max_filesize': 50 * 1024 * 1024
        }
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        
        for file in os.listdir('.'):
            if file.startswith("downloaded_media."):
                await bot.send_document(chat_id=int(target_id), document=types.FSInputFile(file))
                os.remove(file)
                break

        stats_data["downloaded_media"] += 1
        return web.json_response({"status": "success", "message": "Media muvaffaqiyatli yuklab Telegram'ga yuborildi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Yuklashda xatolik: {str(e)}"}, status=400)

# 5. ADVANCED TEXT-TO-SPEECH GENERATOR
async def generate_custom_voice(text, voice_type, output_file):
    if voice_type in ["girl", "child"]:
        voice = "uz-UZ-MadinaNeural"
    elif voice_type in ["boy", "hacker", "robot"]:
        voice = "uz-UZ-SardorNeural"
    else:
        voice = "tr-TR-AhmetNeural"

    temp_file = "temp_raw.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(temp_file)

    audio = AudioSegment.from_file(temp_file)

    if voice_type == "child":
        new_sample_rate = int(audio.frame_rate * 1.35)
        audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(audio.frame_rate)
    elif voice_type == "hacker":
        new_sample_rate = int(audio.frame_rate * 0.78)
        audio = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate}).set_frame_rate(audio.frame_rate)
    elif voice_type == "robot":
        audio = audio.low_pass_filter(1200).high_pass_filter(300)

    audio.export(output_file, format="ogg", codec="libopus")
    if os.path.exists(temp_file):
        os.remove(temp_file)

# 5. TEXT-TO-SPEECH (TTS) API
async def handle_text_to_speech(request):
    try:
        data = await request.json()
        text = data.get("text")
        target_id = data.get("target_id")
        voice_type = data.get("voice_type", "girl")

        filepath = "voice_output.ogg"
        await generate_custom_voice(text, voice_type, filepath)

        await bot.send_voice(chat_id=int(target_id), voice=types.FSInputFile(filepath))
        if os.path.exists(filepath):
            os.remove(filepath)

        return web.json_response({"status": "success", "message": f"Matn '{voice_type}' ovozida yuborildi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

# 6. USERBOT / AUTO-JOIN & AUTO-SPAM API
async def handle_userbot_join_spam(request):
    if not userbot or not userbot.is_connected():
        return web.json_response({"status": "error", "message": "Userbot API_ID va API_HASH sozlanmagan!"}, status=400)

    try:
        data = await request.json()
        group_link = data.get("group_link")
        msg_text = data.get("message")
        count = int(data.get("count", 1))

        entity = await userbot.get_entity(group_link)
        for _ in range(count):
            await userbot.send_message(entity, msg_text)
            await asyncio.sleep(1)

        return web.json_response({"status": "success", "message": f"Userbot {group_link} guruhiga {count} ta xabar yubordi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Userbot xatosi: {str(e)}"}, status=400)

# MAVJUD FUNKSIYALAR
async def handle_send_message(request):
    try:
        data = await request.json()
        target_id = data.get("target_id")
        message_text = data.get("message")

        if not target_id or not message_text:
            return web.json_response({"status": "error", "message": "ID yoki xabar kiritilmadi!"}, status=400)

        await bot.send_message(
            chat_id=int(target_id),
            text=f"💬 **Saytdan kelgan xabar:**\n\n{message_text}",
            parse_mode="Markdown"
        )
        stats_data["sent_messages"] += 1
        return web.json_response({"status": "success", "message": "Xabar muvaffaqiyatli yuborildi!"})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

async def handle_check_channel(request):
    try:
        data = await request.json()
        channel_input = data.get("channel_username", "").strip()

        if not channel_input:
            return web.json_response({"status": "error", "message": "Kanal niknemini kiritmadingiz!"}, status=400)

        if not channel_input.startswith("@") and not channel_input.startswith("-100"):
            channel_input = f"@{channel_input}"

        members_count = await bot.get_chat_member_count(chat_id=channel_input)
        chat_info = await bot.get_chat(chat_id=channel_input)

        admin_niks = []
        try:
            admins = await bot.get_chat_administrators(chat_id=channel_input)
            for admin in admins:
                user = admin.user
                nik = f"@{user.username}" if user.username else f"{user.first_name}"
                admin_niks.append(nik)
        except Exception:
            admin_niks = ["Bot kanalda admin emas."]

        stats_data["checked_channels"] += 1
        return web.json_response({
            "status": "success",
            "title": chat_info.title or channel_input,
            "username": channel_input,
            "members_count": members_count,
            "admins": admin_niks
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Kanal topilmadi: {str(e)}"}, status=400)

async def handle_join_channel(request):
    try:
        data = await request.json()
        channel_input = data.get("channel_username", "").strip()

        if not channel_input.startswith("@") and not channel_input.startswith("-100"):
            channel_input = f"@{channel_input}"

        chat_info = await bot.get_chat(chat_id=channel_input)
        bot_member = await bot.get_chat_member(chat_id=channel_input, user_id=bot.id)

        return web.json_response({
            "status": "success",
            "message": f"Bot <b>{chat_info.title}</b> kanalida ulangan (Mavqe: {bot_member.status})."
        })
    except Exception as e:
        return web.json_response({
            "status": "error",
            "message": f"Bot u yerda yo'q yoki admin emas. Xatolik: {str(e)}"
        }, status=400)

async def handle_spam_channel(request):
    try:
        data = await request.json()
        channel_input = data.get("channel_username", "").strip()
        count = int(data.get("count", 1))
        message_text = data.get("message", "")

        if not channel_input or not message_text:
            return web.json_response({"status": "error", "message": "Ma'lumotlar to'liq emas!"}, status=400)

        if not channel_input.startswith("@") and not channel_input.startswith("-100"):
            channel_input = f"@{channel_input}"

        if count < 1: count = 1
        if count > 1300: count = 1300

        asyncio.create_task(run_bulk_send(channel_input, message_text, count))

        return web.json_response({
            "status": "success",
            "message": f"📢 <b>{channel_input}</b> kanaliga {count} ta xabar yuborish jarayoni boshlandi."
        })
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

async def run_bulk_send(chat_id, text, count):
    for i in range(1, count + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=f"{text} (#{i})")
            await asyncio.sleep(1)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.send_message(chat_id=chat_id, text=f"{text} (#{i})")
        except Exception as e:
            logging.error(f"Xabar yuborishda xatolik: {e}")
            break

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    app.router.add_get('/api/stats', handle_get_stats)
    app.router.add_post('/api/send-msg', handle_send_message)
    app.router.add_post('/api/send-anon', handle_send_anon)
    app.router.add_post('/api/check-channel', handle_check_channel)
    app.router.add_post('/api/join-channel', handle_join_channel)
    app.router.add_post('/api/spam-channel', handle_spam_channel)
    app.router.add_post('/api/forward-posts', handle_forward_posts)
    app.router.add_post('/api/download-media', handle_download_media)
    app.router.add_post('/api/tts', handle_text_to_speech)
    app.router.add_post('/api/userbot-spam', handle_userbot_join_spam)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Salom {message.from_user.first_name}! Mening ID-im: `{message.from_user.id}`", parse_mode="Markdown")

async def main():
    logging.basicConfig(level=logging.INFO)
    if userbot:
        await userbot.start()
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
