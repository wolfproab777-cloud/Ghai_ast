import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Ishchi katalog yo'lini olish
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# index.html faylini ko'rsatuvchi funksiya
async def handle_web(request):
    html_file_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(html_file_path):
        return web.FileResponse(html_file_path)
    return web.Response(text="index.html fayli topilmadi!", status=404)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_web)
    
    # Static fayllar (CSS, JS, rasm) bo'lsa ularni ham ulash
    # app.router.add_static('/static/', path=os.path.join(BASE_DIR, 'static'), name='static')
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Salom {message.from_user.first_name}! Men Ghai boti man.")

@dp.message()
async def chat_handler(message: types.Message):
    await message.answer(f"Ghai: So'rovingiz qabul qilindi -> {message.text}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
