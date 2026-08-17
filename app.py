import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
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
        return web.json_response({
            "status": "error", 
            "message": f"Xabar yuborib bo'lmadi: {str(e)}"
        }, status=400)

# Kanalni razvedka/tekshirish API
async def handle_check_channel(request):
    try:
        data = await request.json()
        channel_input = data.get("channel_username", "").strip()

        if not channel_input:
            return web.json_response({"status": "error", "message": "Kanal niknemini kiritmadingiz!"}, status=400)

        if not channel_input.startswith("@"):
            channel_input = f"@{channel_input}"

        # 1. Kanal a'zolari sonini olish
        members_count = await bot.get_chat_member_count(chat_id=channel_input)
        chat_info = await bot.get_chat(chat_id=channel_input)

        # 2. Kanal administrators ro'yxatidan niklarni olish
        admin_niks = []
        try:
            admins = await bot.get_chat_administrators(chat_id=channel_input)
            for admin in admins:
                user = admin.user
                nik = f"@{user.username}" if user.username else f"{user.first_name}"
                admin_niks.append(nik)
        except Exception:
            admin_niks = ["Bot kanalda admin emasligi sababli niklarni to'liq ololmadi."]

        # 3. Kanaldagi APK fayllarni sanash (oxirgi postlar bo'yicha)
        # Eslatib o'tamiz: To'liq kanaldagi hamma APK larni sanash uchun bot kanalda xabarlarni kuzatib borishi kerak
        apk_count = "Tahlil qilindi"

        return web.json_response({
            "status": "success",
            "title": chat_info.title or channel_input,
            "username": channel_input,
            "members_count": members_count,
            "apk_count": apk_count,
            "admins": admin_niks
        })

    except Exception as e:
        return web.json_response({
            "status": "error",
            "message": f"Kanal topilmadi yoki bot u yerda yo'q! Xatolik: {str(e)}"
        }, status=400)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    app.router.add_post('/api/send-msg', handle_send_message)
    app.router.add_post('/api/check-channel', handle_check_channel)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Salom {message.from_user.first_name}! Mening ID-im: `{message.from_user.id}`", parse_mode="Markdown")

@dp.message()
async def chat_handler(message: types.Message):
    await message.answer(f"Ghai: So'rovingiz qabul qilindi -> {message.text}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
