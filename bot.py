import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
import asyncio

# Токен бота
API_TOKEN = '8323926582:AAF0Nzg0HdhF0_4WrlaOonBA4bLokSJxWWU'

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Создаем инлайн-кнопку
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Наш канал 🌟", 
                    url="https://t.me/basegriefer"
                )
            ]
        ]
    )
    
    welcome_text = "👋 Привет, я храню файлы с канала Dima Griefer!"
    
    await message.answer(welcome_text, reply_markup=keyboard)

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
