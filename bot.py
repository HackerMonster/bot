import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Токен вашего бота (замените на свой)
BOT_TOKEN = "7948105899:AAHsPWxKPd7X9g4oEgzzkxwDQV_I47rTh00"

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Функция обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение при команде /start"""
    user = update.effective_user
    welcome_text = f"🖐️ Привет, {user.first_name}!\n\nЯ простой бот. Рад тебя видеть!"
    
    await update.message.reply_text(welcome_text)

# Основная функция
def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
