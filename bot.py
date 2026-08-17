import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command

# Bot tokenini Render muhitidan (Environment Variable) olamiz
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        f"Salom, {message.from_user.first_name}! Men **Ghai** — sizning shaxsiy Telegram assistentingizman.\n\n"
        "Menga topshiriq bering (masalan: `kanalga yoz: Matn` yoki `id ga yoz: 1234567 | Matn`)."
    )

@dp.message(Command("yordam"))
async def help_handler(message: types.Message):
    await message.answer(
        "**Ghai Bot Buyruqlari:**\n"
        "• `kanalga yoz: [Matn]` — Kanalingizga post joylaydi.\n"
        "• `id ga yoz: [ID] | [Matn]` — Ko'rsatilgan ID ga xabar yuboradi.\n"
        "• `pina: [Matn]` — Kelgan xabarni qadab qo'yadi."
    )

@dp.message()
async def process_task(message: types.Message):
    text = message.text.strip()

    # 1. Kanalga post yuborish topshirig'i
    if text.lower().startswith("kanalga yoz:"):
        post_text = text[12:].strip()
        channel_id = os.getenv("CHANNEL_ID") # @kanal_username yoki ID
        if channel_id:
            try:
                await bot.send_message(chat_id=channel_id, text=post_text)
                await message.answer("Xabar kanalga muvaffaqiyatli joylandi!")
            except Exception as e:
                await message.answer(f"Xatolik: {e}")
        else:
            await message.answer("Kanal ID sozlanmagan!")
        return

    # 2. Aniq Telegram ID ga xabar yuborish
    if text.lower().startswith("id ga yoz:"):
        try:
            raw = text[10:].strip()
            target_id, msg_body = raw.split("|", 1)
            await bot.send_message(chat_id=target_id.strip(), text=msg_body.strip())
            await message.answer("Xabar yetkazildi!")
        except Exception:
            await message.answer("Format noto'g'ri! Misol: `id ga yoz: 123456 | Salom`")
        return

    # 3. Oddiy chat muloqoti (Ghai uslubida javob)
    await message.answer(f"Ghai: Topsiriq qabul qilindi. '{text}' bo'yicha ishlayapman...")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
