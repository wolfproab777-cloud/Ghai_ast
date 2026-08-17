import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiohttp import web

# Bot tokenini olish
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Render porti uchun oddiy web-server javobi
async def handle(request):
    return web.Response(text="Ghai Bot is active!")

# Web-serverni ishga tushirish (Render port xatoligini yo'qotish uchun)
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Salom {message.from_user.first_name}! Men **Ghai** boti man. Sizga qanday yordam bera olaman?")

@dp.message()
async def chat_handler(message: types.Message):
    await message.answer(f"Ghai: So'rovingiz qabul qilindi -> {message.text}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
