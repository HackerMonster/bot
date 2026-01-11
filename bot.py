import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import uuid
from datetime import datetime

# Токен бота
API_TOKEN = '8323926582:AAF0Nzg0HdhF0_4WrlaOonBA4bLokSJxWWU'

# ID каналов для проверки подписки
CHANNELS = [
    {"name": "BaseGriefer", "url": "https://t.me/basegriefer", "username": "basegriefer"},
    {"name": "Chat BaseGriefer", "url": "https://t.me/chatbasegriefer", "username": "chatbasegriefer"}
]

# ID чатов и каналов, где бот НЕ ДОЛЖЕН работать
BLACKLIST_CHAT_IDS = [-1002197945807, -1001621247413]

# ID канала для загрузки файлов (замените на ваш)
FILE_STORAGE_CHAT_ID = -1003285242946

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище файлов (в памяти, можно заменить на БД)
file_storage = {}

class SubscriptionStates(StatesGroup):
    waiting_for_subscription = State()

# Функция для проверки находится ли чат в черном списке
async def is_chat_blacklisted(chat_id: int) -> bool:
    """
    Проверяет, находится ли чат в черном списке
    Возвращает True если бот должен игнорировать этот чат
    """
    if not BLACKLIST_CHAT_IDS:
        try:
            for channel in CHANNELS:
                chat = await bot.get_chat(f"@{channel['username']}")
                BLACKLIST_CHAT_IDS.append(chat.id)
                logging.info(f"Добавлен чат в черный список: {channel['username']} (ID: {chat.id})")
        except Exception as e:
            logging.error(f"Не удалось получить ID чатов: {e}")
    
    if chat_id in BLACKLIST_CHAT_IDS:
        return True
    
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username and chat.username in ["basegriefer", "chatbasegriefer"]:
            BLACKLIST_CHAT_IDS.append(chat_id)
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
            chat_member = await bot.get_chat_member(f"@{channel['username']}", user_id)
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
    try:
        messages_to_delete = []
        
        async for msg in bot.get_chat_history(chat_id, limit=50):
            if msg.from_user and msg.from_user.id == bot.id:
                if msg.text and any(keyword in msg.text for keyword in [
                    "Прежде чем пользоваться ботом",
                    "Подпишитесь на все каналы",
                    "✅ Вы успешно подписались",
                    "❌ Подтверждено:",
                    "⚠️ Подпишитесь на все каналы"
                ]):
                    messages_to_delete.append(msg.message_id)
        
        for msg_id in messages_to_delete:
            try:
                await bot.delete_message(chat_id, msg_id)
                await asyncio.sleep(0.1)
            except Exception as e:
                logging.error(f"Не удалось удалить сообщение {msg_id}: {e}")
        
        logging.info(f"Удалено {len(messages_to_delete)} сообщений о подписке")
        
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщений о подписке: {e}")

# Функция для сохранения информации о файле
def save_file_info(message: Message, file_type: str):
    unique_code = str(uuid.uuid4())[:12]
    
    # Сохраняем основную информацию о сообщении
    file_storage[unique_code] = {
        'message_id': message.message_id,
        'chat_id': message.chat.id,
        'file_type': file_type,
        'caption': message.caption or "",
        'created_at': datetime.now(),
        'uses': 0
    }
    
    # Сохраняем file_id в зависимости от типа файла
    if file_type == "document":
        file_storage[unique_code]['file_id'] = message.document.file_id
        file_storage[unique_code]['file_name'] = message.document.file_name
    elif file_type == "photo":
        file_storage[unique_code]['file_id'] = message.photo[-1].file_id
    elif file_type == "video":
        file_storage[unique_code]['file_id'] = message.video.file_id
    elif file_type == "audio":
        file_storage[unique_code]['file_id'] = message.audio.file_id
    elif file_type == "voice":
        file_storage[unique_code]['file_id'] = message.voice.file_id
    elif file_type == "video_note":
        file_storage[unique_code]['file_id'] = message.video_note.file_id
    elif file_type == "animation":
        file_storage[unique_code]['file_id'] = message.animation.file_id
    elif file_type == "sticker":
        file_storage[unique_code]['file_id'] = message.sticker.file_id
    
    return unique_code

# Функция для получения файла по коду
def get_file_by_code(code):
    if code in file_storage:
        file_storage[code]['uses'] += 1
        return file_storage[code]
    return None

# Обработчик загрузки ЛЮБЫХ файлов в канале -1003285242946
@dp.message(lambda message: message.chat.id == FILE_STORAGE_CHAT_ID)
async def handle_file_upload(message: Message):
    file_type = None
    
    # Определяем тип контента
    if message.document:
        file_type = "document"
    elif message.photo:
        file_type = "photo"
    elif message.video:
        file_type = "video"
    elif message.audio:
        file_type = "audio"
    elif message.voice:
        file_type = "voice"
    elif message.video_note:
        file_type = "video_note"
    elif message.animation:
        file_type = "animation"
    elif message.sticker:
        file_type = "sticker"
    
    # Если это файл (любой тип)
    if file_type:
        # Создаем уникальный код
        unique_code = save_file_info(message, file_type)
        
        # Создаем ссылку
        bot_username = (await bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={unique_code}"
        
        # Создаем кнопку
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👾 Наш Канал",
                        url="https://t.me/basegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📥 Получить файл",
                        url=link
                    )
                ]
            ]
        )
        
        # Отправляем сообщение с кнопкой
        await message.reply(
            f"📁 Файл сохранен!\n\n"
            f"🔗 Ссылка для получения: `{link}`\n\n"
            f"ℹ️ Нажмите кнопку ниже, чтобы перейти к боту",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

# Обработчик команды /start с параметром
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, есть ли параметр в команде start
    if len(message.text.split()) > 1:
        code = message.text.split()[1]
        
        # Проверяем подписку перед выдачей файла
        subscription_status = await check_user_subscription(user_id)
        
        if subscription_status["subscribed_count"] < subscription_status["total_count"]:
            # Пользователь не подписан
            warning_text = (
                "❗ | Для получения файла подпишитесь на каналы!\n\n"
                f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
                "❗ После подписки проверьте еще раз."
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👾 Наш Канал", 
                            url="https://t.me/basegriefer"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="✅ Проверить подписку",
                            callback_data=f"check_and_get_{code}"
                        )
                    ]
                ]
            )
            
            await message.answer(warning_text, reply_markup=keyboard)
            return
        
        # Если подписан - отправляем файл
        file_info = get_file_by_code(code)
        if file_info:
            try:
                # Отправляем файл в зависимости от типа
                if file_info['file_type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_info['file_id']
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_info['file_id']
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'sticker':
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_info['file_id']
                    )
                
                # Показываем статистику
                stats_text = (
                    f"✅ Файл успешно отправлен!\n\n"
                    f"📊 Статистика:\n"
                    f"• Использовано раз: {file_info['uses']}\n"
                    f"• Дата создания: {file_info['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🔗 Для нового файла загрузите его в канал"
                )
                
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="👾 Наш Канал",
                                url="https://t.me/basegriefer"
                            )
                        ]
                    ]
                )
                
                await message.answer(stats_text, reply_markup=keyboard)
                
            except Exception as e:
                await message.answer(f"❌ Ошибка при отправке файла: {str(e)}")
        else:
            await message.answer("❌ Файл не найден или ссылка устарела.")
        return
    
    # Стандартная команда /start без параметра - ВОЗВРАЩАЕМ СТАРОЕ ПРИВЕТСТВИЕ
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        await delete_all_subscription_messages(chat_id)
        
        # СТАРОЕ ПРИВЕТСТВИЕ
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
        await delete_all_subscription_messages(chat_id)
        
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        sent_message = await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        await state.update_data(last_subscription_message_id=sent_message.message_id)
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Обработчик для кнопки "Проверить подписку и получить файл"
@dp.callback_query(lambda c: c.data.startswith("check_and_get_"))
async def check_and_get_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    code = callback_query.data.replace("check_and_get_", "")
    
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Пользователь подписался
        await callback_query.message.delete()
        
        file_info = get_file_by_code(code)
        if file_info:
            try:
                # Отправляем файл в зависимости от типа
                chat_id = callback_query.message.chat.id
                
                if file_info['file_type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_info['file_id']
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_info['file_id']
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_info['file_id'],
                        caption=file_info['caption']
                    )
                elif file_info['file_type'] == 'sticker':
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_info['file_id']
                    )
                
                await callback_query.message.answer("✅ Файл успешно отправлен!")
                
            except Exception as e:
                await callback_query.message.answer(f"❌ Ошибка при отправке файла: {str(e)}")
    else:
        await callback_query.answer("❌ Вы все еще не подписаны на все каналы!", show_alert=True)

# Обработчик нажатия кнопки проверки подписки
@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        await delete_all_subscription_messages(chat_id)
        
        success_message = await callback_query.message.answer(
            "✅ Вы успешно подписались на все каналы! Теперь вы можете пользоваться ботом."
        )
        
        # СТАРОЕ ПРИВЕТСТВИЕ
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
        
        await asyncio.sleep(3)
        try:
            await success_message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить временное сообщение об успехе: {e}")
        
        await state.clear()
    else:
        await delete_all_subscription_messages(chat_id)
        
        warning_text = (
            f"⚠️ Подпишитесь на все каналы.\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        await callback_query.message.answer(warning_text, reply_markup=create_subscription_keyboard())
        
        try:
            await callback_query.message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить старое сообщение: {e}")
    
    await callback_query.answer()

# Мидлварь для проверки всех входящих сообщений
@dp.update.middleware()
async def blacklist_middleware(handler, event: types.Update, data: dict):
    chat_id = None
    
    if event.message:
        chat_id = event.message.chat.id
    elif event.callback_query:
        chat_id = event.callback_query.message.chat.id
    elif event.edited_message:
        chat_id = event.edited_message.chat.id
    
    if chat_id:
        if await is_chat_blacklisted(chat_id):
            logging.info(f"Бот проигнорировал событие в черном списке чата: {chat_id}")
            
            if event.callback_query:
                try:
                    await event.callback_query.answer()
                except:
                    pass
            
            return
    
    return await handler(event, data)

# Проверка подписки для всех сообщений
@dp.message()
async def handle_all_messages(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == SubscriptionStates.waiting_for_subscription.state:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] < subscription_status["total_count"]:
        await delete_all_subscription_messages(chat_id)
        
        warning_text = (
            "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!\n\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        sent_message = await message.answer(warning_text, reply_markup=create_subscription_keyboard())
        await state.update_data(last_subscription_message_id=sent_message.message_id)
        await state.set_state(SubscriptionStates.waiting_for_subscription)

# Основная функция
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
