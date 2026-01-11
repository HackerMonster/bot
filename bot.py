import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio

# Токен бота
API_TOKEN = '8323926582:AAF0Nzg0HdhF0_4WrlaOonBA4bLokSJxWWU'

# ID каналов для проверки подписки
CHANNELS = [
    {"name": "BaseGriefer", "url": "https://t.me/basegriefer", "username": "basegriefer"},
    {"name": "Chat BaseGriefer", "url": "https://t.me/chatbasegriefer", "username": "chatbasegriefer"}
]

# Каналы и группы, где бот не должен работать (по username или ID)
BLACKLIST_CHATS = ["@basegriefer", "@chatbasegriefer", "basegriefer", "chatbasegriefer"]

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class SubscriptionStates(StatesGroup):
    waiting_for_subscription = State()

# Проверка, находится ли сообщение в черном списке чатов
def is_blacklisted_chat(chat_username: str = None, chat_id: int = None) -> bool:
    """
    Проверяет, находится ли чат в черном списке
    """
    # Если передан username, проверяем его
    if chat_username:
        for blacklisted in BLACKLIST_CHATS:
            if blacklisted.lower() in chat_username.lower():
                return True
    
    # Здесь можно добавить проверку по ID чата, если нужно
    # if chat_id and chat_id in BLACKLIST_IDS:
    #     return True
    
    return False

# Получение username чата
async def get_chat_username(chat_id: int) -> str:
    """
    Получает username чата по его ID
    """
    try:
        chat = await bot.get_chat(chat_id)
        return chat.username if chat.username else f"chat_{chat_id}"
    except Exception as e:
        logging.error(f"Ошибка при получении информации о чате {chat_id}: {e}")
        return f"chat_{chat_id}"

# Функция для создания клавиатуры с кнопками подписки
def create_subscription_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1️⃣ Подписаться", 
                    url=CHANNELS[0]["url"]
                )
            ],
            [
                InlineKeyboardButton(
                    text="2️⃣ Подписаться", 
                    url=CHANNELS[1]["url"]
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription"
                )
            ]
        ]
    )
    return keyboard

# Функция для проверки подписки пользователя
async def check_user_subscription(user_id: int) -> dict:
    subscribed_count = 0
    not_subscribed = []
    
    for channel in CHANNELS:
        try:
            # Проверяем подписку через get_chat_member
            chat_member = await bot.get_chat_member(f"@{channel['username']}", user_id)
            # Проверяем статус подписки
            if chat_member.status in ["member", "administrator", "creator"]:
                subscribed_count += 1
            else:
                not_subscribed.append(channel["name"])
        except Exception as e:
            logging.error(f"Ошибка при проверке подписки на канал {channel['name']}: {e}")
            not_subscribed.append(channel["name"])
    
    return {
        "subscribed_count": subscribed_count,
        "total_count": len(CHANNELS),
        "not_subscribed": not_subscribed
    }

# Мидлварь для проверки черного списка чатов
@dp.message.middleware()
async def blacklist_middleware(handler, event: Message, data: dict):
    # Получаем username чата
    chat_username = await get_chat_username(event.chat.id)
    
    # Проверяем, находится ли чат в черном списке
    if is_blacklisted_chat(chat_username):
        logging.info(f"Бот проигнорировал сообщение в черном списке чата: {chat_username}")
        return  # Прерываем обработку
    
    # Продолжаем обработку
    return await handler(event, data)

# Мидлварь для колбэков (нажатия кнопок)
@dp.callback_query.middleware()
async def blacklist_callback_middleware(handler, event: CallbackQuery, data: dict):
    # Получаем username чата
    chat_username = await get_chat_username(event.message.chat.id)
    
    # Проверяем, находится ли чат в черном списке
    if is_blacklisted_chat(chat_username):
        logging.info(f"Бот проигнорировал колбэк в черном списке чата: {chat_username}")
        return  # Прерываем обработку
    
    # Продолжаем обработку
    return await handler(event, data)

# Стартовая команда
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Пользователь подписан на все каналы
        welcome_text = "👋 Привет, я храню файлы с канала Dima Griefer!"
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
        await message.answer(welcome_text, reply_markup=keyboard)
    else:
        # Пользователь не подписан
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Обработчик нажатия кнопки проверки подписки
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Пользователь подписан на все каналы
        try:
            # Удаляем предыдущее сообщение с проверкой подписки
            await callback_query.message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить сообщение: {e}")
        
        # Отправляем сообщение об успешной проверке (которое удалим через 2 секунды)
        success_message = await callback_query.message.answer("✅ Вы успешно подписались на все каналы!")
        
        # Отправляем основное приветственное сообщение
        welcome_text = "👋 Привет, я храню файлы с канала Dima Griefer!"
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
        await callback_query.message.answer(welcome_text, reply_markup=keyboard)
        
        # Удаляем временное сообщение об успехе через 2 секунды
        await asyncio.sleep(2)
        try:
            await success_message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить временное сообщение: {e}")
        
        await state.clear()
    else:
        # Пользователь все еще не подписан
        warning_text = (
            f"⚠️ Подпишитесь на все каналы.\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        await callback_query.message.edit_text(warning_text, reply_markup=create_subscription_keyboard())
    
    await callback_query.answer()

# Проверка подписки для всех сообщений (кроме команды /start)
@dp.message()
async def handle_all_messages(message: Message, state: FSMContext):
    # Если пользователь в процессе подписки, игнорируем
    current_state = await state.get_state()
    if current_state == SubscriptionStates.waiting_for_subscription.state:
        return
    
    user_id = message.from_user.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] < subscription_status["total_count"]:
        # Удаляем предыдущие сообщения бота о подписке от этого пользователя
        try:
            # Получаем чат
            chat_id = message.chat.id
            user_bot_messages = []
            
            # Проверяем последние 10 сообщений (можно увеличить)
            async for msg in bot.get_chat_history(chat_id, limit=10):
                if msg.from_user.id == bot.id and msg.text and (
                    "Прежде чем пользоваться ботом" in msg.text or 
                    "Подпишитесь на все каналы" in msg.text
                ):
                    user_bot_messages.append(msg.message_id)
            
            # Удаляем найденные сообщения (кроме самого нового)
            if len(user_bot_messages) > 1:
                for msg_id in user_bot_messages[:-1]:  # Удаляем все, кроме последнего
                    try:
                        await bot.delete_message(chat_id, msg_id)
                    except Exception as e:
                        logging.error(f"Не удалось удалить сообщение {msg_id}: {e}")
        except Exception as e:
            logging.error(f"Ошибка при очистке старых сообщений: {e}")
        
        # Пользователь не подписан - отправляем новое сообщение
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Обработчик для игнорирования сообщений в группах и каналах
@dp.message(lambda message: message.chat.type in ["group", "supergroup", "channel"])
async def ignore_group_messages(message: Message):
    """
    Игнорирует сообщения в группах и каналах (кроме личных сообщений)
    """
    # Для групп и каналов бот отвечает только на команды
    # или можно полностью игнорировать
    pass

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
