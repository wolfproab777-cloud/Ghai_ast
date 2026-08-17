import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

async def handle_web(request):
    html_file_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(html_file_path):
        return web.FileResponse(html_file_path)
    return web.Response(text="index.html fayli topilmadi!", status=404)

# ID orqali xabar yuborish API
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
        return web.json_response({"status": "success", "message": "Xabar muvaffaqiyatli yuborildi!"})

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

# Kanalni razvedka qilish API
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

        return web.json_response({
            "status": "success",
            "title": chat_info.title or channel_input,
            "username": channel_input,
            "members_count": members_count,
            "admins": admin_niks
        })

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Kanal topilmadi yoki bot u yerda yo'q: {str(e)}"}, status=400)

# FUNKSIYA 1: Kanal/Guruhga obuna bo'lish holatini tekshirish
async def handle_join_channel(request):
    try:
        data = await request.json()
        channel_input = data.get("channel_username", "").strip()

        if not channel_input.startswith("@") and not channel_input.startswith("-100"):
            channel_input = f"@{channel_input}"

        chat_info = await bot.get_chat(chat_id=channel_input)
        
        # Telegram API botlarni o'zi avto-join bo'lishiga ruxsat bermaydi.
        # Bot guruh/kanalda mavjudligini va adminligini tekshiradi.
        bot_member = await bot.get_chat_member(chat_id=channel_input, user_id=bot.id)

        return web.json_response({
            "status": "success",
            "message": f" Bot <b>{chat_info.title}</b> kanalida ulangan (Mavqe: {bot_member.status})."
        })
    except Exception as e:
        return web.json_response({
            "status": "error",
            "message": f"Bot bu kanalga ulana olmadi! Botingizni o'sha kanal/guruhga qo'shib, admin huquqini bering. Xatolik: {str(e)}"
        }, status=400)

# FUNKSIYA 2: Kanal/Guruhga ko'p miqdorda xabar yuborish (Spam / Auto-Send)
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
        if count > 1300: count = 1300  # Maksimal 1300 ta

        # Xabarlarni orqa fonda (asyncio task) yuborish
        asyncio.create_task(run_bulk_send(channel_input, message_text, count))

        return web.json_response({
            "status": "success",
            "message": f"🚀 <b>{channel_input}</b> kanaliga {count} ta xabar yuborish jarayoni boshlandi (har 1 soniyada)."
        })

    except Exception as e:
        return web.json_response({"status": "error", "message": f"Xatolik: {str(e)}"}, status=400)

# Ketma-ket yuborish mantiqi (FloodWait xavfsizligi bilan)
async def run_bulk_send(chat_id, text, count):
    for i in range(1, count + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=f"{text} (#{i})")
            await asyncio.sleep(1)  # Har 1 soniyada
        except TelegramRetryAfter as e:
            # Telegram kutishni talab qilsa kutiladi
            await asyncio.sleep(e.retry_after)
            await bot.send_message(chat_id=chat_id, text=f"{text} (#{i})")
        except Exception as e:
            logging.error(f"Xabar yuborishda xatolik: {e}")
            break

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    app.router.add_post('/api/send-msg', handle_send_message)
    app.router.add_post('/api/check-channel', handle_check_channel)
    app.router.add_post('/api/join-channel', handle_join_channel)
    app.router.add_post('/api/spam-channel', handle_spam_channel)
    
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
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
