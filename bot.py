import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
import asyncio

# Токен вашего бота
BOT_TOKEN = "8323926582:AAF0Nzg0HdhF0_4WrlaOonBA4bLokSJxWWU"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    # Создаем приветственное сообщение с ASCII-артом
    welcome_text = """
┌─────────────────────
│  👋 ПРИВЕТСТВУЕМ!
│  Добро пожаловать в лучший
│  источник контента для Minecraft!
└─────────────────────

📥 <b>ОСНОВНАЯ ФУНКЦИЯ:</b>
│
├─ ✅ Бесплатные моды и файлы
├─ ✅ Огромная библиотека
├─ ✅ Расширенный функционал
│
└─ 😏 <b>ДЛЯ ЧЕГО ЭТО?</b>
├─ 🎯 Для работы: Создавай сложные проекты
└─ 🎮 Для веселья: Открывай новые способы игры!
"""
    
    # Отправляем сообщение пользователю
    await message.answer(welcome_text)

# Функция для запуска бота
async def main():
    logging.info("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
