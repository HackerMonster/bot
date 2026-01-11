import os
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен вашего бота (получите у @BotFather)
TOKEN = "7948105899:AAHsPWxKPd7X9g4oEgzzkxwDQV_I47rTh00"

# Папка для сохранения файлов
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Словарь для хранения соответствий: file_id -> уникальный код
file_database = {}

async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"Привет {user.first_name}! Отправь мне фото, и я дам тебе уникальную ссылку на него.\n"
        f"Мой создатель: @MERIXTI"
    )

async def handle_photo(update: Update, context: CallbackContext) -> None:
    """Обработчик фотографий"""
    try:
        # Получаем фото с максимальным качеством
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # Генерируем уникальный код
        unique_code = str(uuid.uuid4())[:16]
        
        # Сохраняем в базу
        file_database[unique_code] = file_id
        
        # Создаем ссылку
        bot_username = context.bot.username
        link = f"https://t.me/{bot_username}?start={unique_code}"
        
        # Создаем кнопку с ссылкой
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📎 Открыть фото", url=link)]
        ])
        
        await update.message.reply_text(
            f"✅ Фото сохранено!\n"
            f"🔗 Ваша ссылка: `{link}`\n"
            f"📎 Код: `{unique_code}`",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке фото")

async def handle_start_with_code(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start с кодом"""
    args = context.args
    if args:
        code = args[0]
        if code in file_database:
            file_id = file_database[code]
            
            # Отправляем фото пользователю
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=file_id,
                caption=f"📸 Фото по коду: {code}"
            )
        else:
            await update.message.reply_text("❌ Фото не найдено или ссылка устарела")
    else:
        await start(update, context)

async def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help"""
    await update.message.reply_text(
        "📸 **Как использовать бота:**\n\n"
        "1. Просто отправьте мне любое фото\n"
        "2. Я сохраню его и дам вам уникальную ссылку\n"
        "3. Отправьте эту ссылку друзьям\n"
        "4. При переходе по ссылке откроется это фото\n\n"
        "🤖 Бот создан по примеру @MERIXTI_files_bot",
        parse_mode='Markdown'
    )

def main() -> None:
    """Основная функция запуска бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", handle_start_with_code))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Запускаем бота
    print("🤖 Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
