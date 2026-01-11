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

# ID чатов и каналов, где бот НЕ ДОЛЖЕН работать
# Получите ID этих чатов с помощью бота @username_to_id_bot или @getidsbot
BLACKLIST_CHAT_IDS = [-1002197945807, -1001621247413]  # Замените на реальные ID

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class SubscriptionStates(StatesGroup):
    waiting_for_subscription = State()

# Функция для проверки находится ли чат в черном списке
async def is_chat_blacklisted(chat_id: int) -> bool:
    """
    Проверяет, находится ли чат в черном списке
    Возвращает True если бот должен игнорировать этот чат
    """
    # Если BLACKLIST_CHAT_IDS пуст, попробуем определить ID автоматически
    if not BLACKLIST_CHAT_IDS:
        # Пробуем получить информацию о каналах и проверить их ID
        try:
            for channel in CHANNELS:
                chat = await bot.get_chat(f"@{channel['username']}")
                BLACKLIST_CHAT_IDS.append(chat.id)
                logging.info(f"Добавлен чат в черный список: {channel['username']} (ID: {chat.id})")
        except Exception as e:
            logging.error(f"Не удалось получить ID чатов: {e}")
    
    # Проверяем, находится ли chat_id в черном списке
    if chat_id in BLACKLIST_CHAT_IDS:
        return True
    
    # Дополнительная проверка по username (если не нашли по ID)
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username and chat.username in ["basegriefer", "chatbasegriefer"]:
            BLACKLIST_CHAT_IDS.append(chat_id)  # Запоминаем ID для будущих проверок
            return True
    except Exception as e:
        logging.error(f"Ошибка при проверке чата {chat_id}: {e}")
    
    return False

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

# Функция для удаления всех сообщений бота о подписке
async def delete_all_subscription_messages(chat_id: int):
    """
    Удаляет все сообщения бота о подписке в указанном чате
    """
    try:
        messages_to_delete = []
        
        # Проверяем последние 50 сообщений в чате
        async for msg in bot.get_chat_history(chat_id, limit=50):
            # Если сообщение от бота
            if msg.from_user and msg.from_user.id == bot.id:
                # Проверяем текст сообщения
                if msg.text and any(keyword in msg.text for keyword in [
                    "Прежде чем пользоваться ботом",
                    "Подпишитесь на все каналы",
                    "✅ Вы успешно подписались",
                    "❌ Подтверждено:",
                    "⚠️ Подпишитесь на все каналы"
                ]):
                    messages_to_delete.append(msg.message_id)
        
        # Удаляем все найденные сообщения
        for msg_id in messages_to_delete:
            try:
                await bot.delete_message(chat_id, msg_id)
                await asyncio.sleep(0.1)  # Небольшая задержка, чтобы не превысить лимиты
            except Exception as e:
                logging.error(f"Не удалось удалить сообщение {msg_id}: {e}")
        
        logging.info(f"Удалено {len(messages_to_delete)} сообщений о подписке")
        
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщений о подписке: {e}")

# Мидлварь для проверки всех входящих сообщений
@dp.update.middleware()
async def blacklist_middleware(handler, event: types.Update, data: dict):
    chat_id = None
    
    # Определяем chat_id в зависимости от типа события
    if event.message:
        chat_id = event.message.chat.id
    elif event.callback_query:
        chat_id = event.callback_query.message.chat.id
    elif event.edited_message:
        chat_id = event.edited_message.chat.id
    
    # Если определили chat_id, проверяем черный список
    if chat_id:
        if await is_chat_blacklisted(chat_id):
            logging.info(f"Бот проигнорировал событие в черном списке чата: {chat_id}")
            
            # Для callback_query нужно ответить, чтобы не висела "часик"
            if event.callback_query:
                try:
                    await event.callback_query.answer()
                except:
                    pass
            
            return  # Полностью прерываем обработку
    
    # Продолжаем обработку если чат не в черном списке
    return await handler(event, data)

# Стартовая команда (будет игнорироваться в черном списке благодаря middleware)
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Удаляем все старые сообщения о подписке
        await delete_all_subscription_messages(chat_id)
        
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
        # Удаляем старые сообщения о подписке перед отправкой нового
        await delete_all_subscription_messages(chat_id)
        
        # Пользователь не подписан
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        sent_message = await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        # Сохраняем ID последнего сообщения о подписке
        await state.update_data(last_subscription_message_id=sent_message.message_id)
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Обработчик нажатия кнопки проверки подписки
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Пользователь подписан на все каналы
        # Удаляем ВСЕ сообщения бота о подписке
        await delete_all_subscription_messages(chat_id)
        
        # Отправляем временное сообщение об успехе (оно само удалится)
        success_message = await callback_query.message.answer(
            "✅ Вы успешно подписались на все каналы! Теперь вы можете пользоваться ботом."
        )
        
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
        
        # Удаляем временное сообщение об успехе через 3 секунды
        await asyncio.sleep(3)
        try:
            await success_message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить временное сообщение об успехе: {e}")
        
        await state.clear()
    else:
        # Пользователь все еще не подписан
        # Удаляем предыдущие сообщения о подписке перед обновлением
        await delete_all_subscription_messages(chat_id)
        
        # Отправляем новое сообщение о необходимости подписки
        warning_text = (
            f"⚠️ Подпишитесь на все каналы.\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        # Отправляем новое сообщение вместо редактирования старого
        await callback_query.message.answer(warning_text, reply_markup=create_subscription_keyboard())
        
        # Пытаемся удалить старое сообщение с кнопкой
        try:
            await callback_query.message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить старое сообщение: {e}")
    
    await callback_query.answer()

# Проверка подписки для всех сообщений (кроме команды /start)
@dp.message()
async def handle_all_messages(message: Message, state: FSMContext):
    # Если пользователь в процессе подписки, игнорируем
    current_state = await state.get_state()
    if current_state == SubscriptionStates.waiting_for_subscription.state:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем подписку
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] < subscription_status["total_count"]:
        # Пользователь не подписан
        
        # Удаляем все предыдущие сообщения о подписке
        await delete_all_subscription_messages(chat_id)
        
        # Отправляем новое сообщение о подписке
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        sent_message = await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        # Сохраняем ID последнего сообщения о подписке
        await state.update_data(last_subscription_message_id=sent_message.message_id)
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
