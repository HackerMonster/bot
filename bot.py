import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
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
    # Формируем приветственное сообщение с форматированием
    welcome_text = (
        "┌─────────────────────\n"
        "│  👋 ПРИВЕТСТВУЕМ!\n"
        "│  Добро пожаловать в лучший\n"
        "│  источник контента для Minecraft!\n"
        "└─────────────────────\n\n"
        "📥 ОСНОВНАЯ ФУНКЦИЯ:\n"
        "│\n"
        "├─ ✅ Бесплатные моды и файлы\n"
        "├─ ✅ Огромная библиотека\n"
        "├─ ✅ Расширенный функционал\n"
        "│\n"
        "└─ 😏 ДЛЯ ЧЕГО ЭТО?\n"
        "├─ 🎯 Для работы: Создавай сложные проекты\n"
        "└─ 🎮 Для веселья: Открывай новые способы игры!"
    )
    
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
