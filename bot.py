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
    {"name": "BaseGriefer", "url": "https://t.me/basegriefer"},
    {"name": "Chat BaseGriefer", "url": "https://t.me/chatbasegriefer"}
]

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class SubscriptionStates(StatesGroup):
    waiting_for_subscription = State()

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
            # Извлекаем username канала из URL
            channel_username = channel["url"].split('/')[-1]
            # Получаем информацию о чате
            chat_member = await bot.get_chat_member(f"@{channel_username}", user_id)
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
        success_text = "✅ Вы успешно подписались на все каналы! Теперь вы можете пользоваться ботом."
        await callback_query.message.answer(success_text)
        
        # Отправляем основное меню
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
        # Пользователь не подписан
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
