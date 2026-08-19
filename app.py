import os
import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web
import yt_dlp
import telethon
from telethon import TelegramClient
import edge_tts
from pydub import AudioSegment

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

userbot = None
if API_ID and API_HASH:
    userbot = TelegramClient('userbot_session', int(API_ID), API_HASH)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

async def handle_get_stats(request):
    return web.json_response({
        "status": "success",
        "stats": stats_data
    })

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

async def handle_talking_photo(request):
    try:
        reader = await request.multipart()
        image_bytes = None
        text = ""
        target_id = ""

        while True:
            field = await reader.next()
            if not field:
                break
            if field.name == 'image':
                image_bytes = await field.read()
            elif field.name == 'text':
                text = await field.read_decode()
            elif field.name == 'target_id':
                target_id = await field.read_decode()

        if not image_bytes or not text or not target_id:
            return web.json_response({"status": "error", "message": "Rasm, matn yoki Telegram ID to'liq kiritilmadi!"}, status=400)

        if not REPLICATE_API_TOKEN:
            return web.json_response({"status": "error", "message": "REPLICATE_API_TOKEN sozlanmagan! Render Environment bo'limini tekshiring."}, status=400)

        image_path = "temp_photo.jpg"
        audio_mp3 = "temp_voice.mp3"
        audio_wav = "temp_voice.wav"

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        communicate = edge_tts.Communicate(text, "uz-UZ-MadinaNeural")
        await communicate.save(audio_mp3)

        sound = AudioSegment.from_file(audio_mp3)
        sound.export(audio_wav, format="wav")

        import base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        with open(audio_wav, "rb") as f:
            aud_b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "version": "3aa0013d2531e21b7776cb67140e10f13f1737e4ba397a6f272a85eb803a62d8",
            "input": {
                "source_image": f"data:image/jpeg;base64,{img_b64}",
                "driven_audio": f"data:audio/wav;base64,{aud_b64}"
            }
        }

        res = requests.post("https://api.replicate.com/v1/predictions", headers=headers, json=payload)
        prediction = res.json()
        prediction_id = prediction.get("id")

        if not prediction_id:
            error_details = prediction.get("detail", "Noma'lum xatolik")
            return web.json_response({"status": "error", "message": f"Replicate API xatosi: {error_details}"}, status=400)

        video_url = None
        for _ in range(40):
            await asyncio.sleep(3)
            chk_res = requests.get(f"https://api.replicate.com/v1/predictions/{prediction_id}", headers=headers)
            chk_data = chk_res.json()
            if chk_data.get("status") == "succeeded":
                video_url = chk_data.get("output")
                break
            elif chk_data.get("status") in ["failed", "canceled"]:
                break

        for f in [image_path, audio_mp3, audio_wav]:
            if os.path.exists(f): 
                os.remove(f)

        if video_url:
            await bot.send_video(chat_id=int(target_id), video=video_url, caption=f"🎬 **Yaratilgan Video:**\n{text}", parse_mode="Markdown")
            stats_data["sent_messages"] += 1
            return web.json_response({"status": "success", "message": "✅ Video yaratildi va Telegram ID ga yuborildi!"})
        else:
            return web.json_response({"status": "error", "message": "❌ Video generatsiyasi muvaffaqiyatsiz tugadi."}, status=400)

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Server xatoligi: {str(e)}"}, status=500)

# PROFIL ANALIZATORI API
async def handle_analyze_profile(request):
    if not userbot or not userbot.is_connected():
        return web.json_response({"status": "error", "message": "Userbot API_ID va API_HASH sozlanmagan!"}, status=400)

    try:
        data = await request.json()
        target = data.get("target", "").strip()

        if not target:
            return web.json_response({"status": "error", "message": "Target kiritilmadi!"}, status=400)

        if target.isdigit():
            user = await userbot.get_entity(int(target))
        else:
            if not target.startswith("@"): target = f"@{target}"
            user = await userbot.get_entity(target)

        full_user = await userbot(telethon.functions.users.GetFullUserRequest(user))

        profile_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "bio": full_user.full_user.about,
            "status": str(type(user.status).__name__).replace("UserStatus", ""),
            "is_bot": user.bot
        }

        stats_data["sent_messages"] += 1
        return web.json_response({"status": "success", "profile": profile_data})

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Profilni analiz qilishda xatolik: {str(e)}"}, status=400)

# POST REJALASHTIRISH API
async def handle_schedule_post(request):
    try:
        data = await request.json()
        target = data.get("target")
        message_text = data.get("message")
        delay = int(data.get("delay", 10))

        if not target or not message_text:
            return web.json_response({"status": "error", "message": "Ma'lumot to'liq emas!"}, status=400)

        asyncio.create_task(run_scheduled_send(target, message_text, delay))

        return web.json_response({"status": "success", "message": f"✅ Post rejalashtirildi! {delay} soniyadan so'ng yuboriladi."})
    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

async def run_scheduled_send(target, text, delay):
    await asyncio.sleep(delay)
    try:
        if target.isdigit() or target.startswith("-"):
            await bot.send_message(chat_id=int(target), text=text)
        else:
            if not target.startswith("@"): target = f"@{target}"
            await bot.send_message(chat_id=target, text=text)
        stats_data["sent_messages"] += 1
    except Exception as e:
        logging.error(f"Rejalashtirilgan xabar yuborishda xatolik: {e}")

async def handle_send_message(request):
    try:
        data = await request.json()
        target_id = data.get("target_id")
        message_text = data.get("message")

        if not target_id or not message_text:
            return web.json_response({"status": "error", "message": "ID yoki xabar kiritilmadi!"}, status=400)

        await bot.send_message(
            chat_id=int(target_id),
            text=f"✉️ **Saytdan kelgan xabar:**\n\n{message_text}",
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
            "message": f"📣 <b>{channel_input}</b> kanaliga {count} ta xabar yuborish jarayoni boshlandi."
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
    app.router.add_post('/api/talking-photo', handle_talking_photo)
    app.router.add_post('/api/analyze-profile', handle_analyze_profile)
    app.router.add_post('/api/schedule-post', handle_schedule_post)

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
