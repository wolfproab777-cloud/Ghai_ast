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

# index.html faylini ko'rsatish
async def handle_web(request):
    html_file_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(html_file_path):
        return web.FileResponse(html_file_path)
    return web.Response(text="index.html fayli topilmadi!", status=404)

# Saytdan kelgan ID va xabarni Telegram'ga yuborish API-si
async def handle_send_message(request):
    try:
        data = await request.json()
        target_id = data.get("target_id")
        message_text = data.get("message")

        if not target_id or not message_text:
            return web.json_response({"status": "error", "message": "ID yoki xabar kiritilmadi!"}, status=400)

        # Telegram bot orqali ko'rsatilgan ID'ga xabar yuborish
        await bot.send_message(
            chat_id=int(target_id),
            text=f"💬 **Saytdan kelgan xabar:**\n\n{message_text}",
            parse_mode="Markdown"
        )
        return web.json_response({"status": "success", "message": "Xabar muvaffaqiyatli yuborildi!"})

    except Exception as e:
        return web.json_response({
            "status": "error", 
            "message": f"Xabar yuborib bo'lmadi! Sababi: {str(e)}. (Foydalanuvchi botga /start bosganiga ishonch hosil qiling)."
        }, status=400)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    app.router.add_post('/api/send-msg', handle_send_message)
    
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
