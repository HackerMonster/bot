import logging
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatMemberStatus

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7948105899:AAHsPWxKPd7X9g4oEgzzkxwDQV_I47rTh00"  # Замените на токен вашего бота

# Список каналов для проверки подписки
CHANNELS_TO_CHECK = [
    "@steal_a_braiinrotai",  # Ваш канал с username
    -1002987239953,          # Ваш канал с ID (уже как число)
]

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, подписан ли пользователь на все необходимые каналы"""
    for channel in CHANNELS_TO_CHECK:
        try:
            # Получаем информацию о статусе пользователя в канале
            chat_member = await context.bot.get_chat_member(
                chat_id=channel, 
                user_id=user_id
            )
            
            # Проверяем статус подписки
            if chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]:
                logger.info(f"Пользователь {user_id} не подписан на {channel}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки на {channel}: {e}")
            return False
    
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    logger.info(f"Пользователь {user.id} ({user.username}) запустил бота")
    
    # Проверяем подписку
    is_subscribed = await check_subscription(user.id, context)
    
    if not is_subscribed:
        # Создаем клавиатуру с кнопками для подписки
        buttons = []
        
        # Для первого канала (username)
        try:
            chat1 = await context.bot.get_chat("@steal_a_braiinrotai")
            channel1_name = chat1.title if chat1.title else "steal_a_braiinrotai"
            buttons.append([InlineKeyboardButton(
                text=f"📢 Подписаться на {channel1_name}",
                url=f"https://t.me/steal_a_braiinrotai"
            )])
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
            buttons.append([InlineKeyboardButton(
                text="📢 Подписаться на steal_a_braiinrotai",
                url="https://t.me/steal_a_braiinrotai"
            )])
        
        # Для второго канала (ID)
        try:
            chat2 = await context.bot.get_chat(-1002987239953)
            channel2_name = chat2.title if chat2.title else "Второй канал"
            buttons.append([InlineKeyboardButton(
                text=f"📢 Подписаться на {channel2_name}",
                url=f"https://t.me/c/{str(-1002987239953)[4:]}"  # Формат ссылки для ID
            )])
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале 2: {e}")
            # Альтернативный способ создания ссылки
            buttons.append([InlineKeyboardButton(
                text="📢 Подписаться на канал 2",
                url="https://t.me/+example"  # Нужна публичная ссылка
            )])
        
        # Добавляем кнопку проверки подписки
        buttons.append([InlineKeyboardButton(
            text="✅ Я подписался! Проверить",
            callback_data="check_subscription"
        )])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "⚠️ Для использования бота необходимо подписаться на наши каналы:\n\n"
            "1. @steal_a_braiinrotai\n"
            "2. Основной канал\n\n"
            "После подписки нажмите кнопку '✅ Я подписался! Проверить'",
            reply_markup=keyboard
        )
    else:
        # Пользователь подписан на все каналы
        await update.message.reply_text(
            f"Привет, {user.first_name}! 🖐️\n\n"
            "Добро пожаловать в наш бот! 🤖\n"
            "✅ Вы успешно прошли проверку подписки!\n\n"
            "Теперь вы можете пользоваться ботом!"
        )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатия кнопки проверки подписки"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    logger.info(f"Пользователь {user.id} нажал проверку подписки")
    
    if query.data == "check_subscription":
        # Проверяем подписку
        is_subscribed = await check_subscription(user.id, context)
        
        if is_subscribed:
            # Удаляем предыдущее сообщение с кнопками
            try:
                await query.delete_message()
            except:
                pass
            
            # Отправляем приветствие
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Привет, {user.first_name}! 🖐️\n\n"
                     "✅ Спасибо за подписку!\n"
                     "Добро пожаловать в наш бот! 🤖\n\n"
                     "Теперь вы можете пользоваться всеми функциями бота!"
            )
        else:
            # Пользователь все еще не подписан
            await query.edit_message_text(
                text=f"❌ {user.first_name}, вы еще не подписались на все каналы!\n\n"
                     "Пожалуйста, убедитесь что вы подписались на:\n"
                     "1. @steal_a_braiinrotai\n"
                     "2. Второй канал\n\n"
                     "После подписки нажмите кнопку проверки еще раз.",
                reply_markup=query.message.reply_markup
            )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    await update.message.reply_text(
        "Список команд:\n"
        "/start - Начать работу с ботом\n"
        "/help - Получить справку\n\n"
        "Если возникли проблемы с проверкой подписки:\n"
        "1. Убедитесь что подписались на оба канала\n"
        "2. Нажмите кнопку '✅ Я подписался! Проверить'\n"
        "3. Если не помогает, перезапустите бота командой /start"
    )

def main() -> None:
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Регистрируем обработчик callback-запросов
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(check_subscription_callback))
    
    # Запускаем бота
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
