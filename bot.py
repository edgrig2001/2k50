import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

TOKEN = "ВАШ_ТОКЕН"

dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Это 2К50.\n"
        "Место для развития, общения и поддержки."
    )

@dp.message()
async def echo(message: Message):
    await message.answer(
        f"Ты написал:\n\n{message.text}"
    )

async def main():
    bot = Bot(TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())