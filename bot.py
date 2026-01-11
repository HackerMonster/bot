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

# Разрешенные пользователи для команды /addfile
ALLOWED_USERS = [
    5870949629,  # ID пользователя
    "Feop06"     # Username пользователя
]

# ID чатов и каналов, где бот НЕ ДОЛЖЕН работать
BLACKLIST_CHAT_IDS = [-1002197945807, -1001621247413]

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище файлов (в памяти)
file_storage = {}

class FileUploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_subscription = State()

# Проверка доступа пользователя к команде /addfile
def is_user_allowed(user_id: int, username: str = None) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к команде /addfile
    """
    # Проверка по ID
    if user_id in ALLOWED_USERS:
        return True
    
    # Проверка по username
    if username and username in ALLOWED_USERS:
        return True
    
    # Проверяем если username есть в ALLOWED_USERS как строка
    if username and username.lower() in [str(u).lower() for u in ALLOWED_USERS if isinstance(u, str)]:
        return True
    
    return False

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
def save_file_info(file_data: dict, file_type: str):
    unique_code = str(uuid.uuid4())[:12]
    
    # Сохраняем основную информацию о файле
    file_storage[unique_code] = {
        'file_type': file_type,
        'file_data': file_data,
        'created_at': datetime.now(),
        'uses': 0
    }
    
    logging.info(f"Файл сохранен с кодом: {unique_code}, тип: {file_type}")
    return unique_code

# Функция для получения файла по коду
def get_file_by_code(code):
    if code in file_storage:
        file_storage[code]['uses'] += 1
        return file_storage[code]
    return None

# НОВАЯ КОМАНДА: /addfile - только для разрешенных пользователей
@dp.message(Command("addfile"))
async def cmd_addfile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    logging.info(f"Команда /addfile от пользователя {user_id} (@{username})")
    
    # Проверяем доступ пользователя
    if not is_user_allowed(user_id, username):
        logging.info(f"Пользователь {user_id} (@{username}) не имеет доступа к команде /addfile")
        # Для остальных пользователей команда ничего не делает (не отвечает)
        return
    
    # У пользователя есть доступ
    logging.info(f"Пользователь {user_id} (@{username}) имеет доступ к команде /addfile")
    
    await message.answer("📤 Отправьте файл, который хотите добавить в базу.")
    await state.set_state(FileUploadStates.waiting_for_file)

# Обработчик получения файла после команды /addfile
@dp.message(FileUploadStates.waiting_for_file)
async def handle_file_upload(message: Message, state: FSMContext):
    file_type = None
    file_data = {}
    
    # Определяем тип контента и собираем данные
    if message.document:
        file_type = "document"
        file_data = {
            'file_id': message.document.file_id,
            'file_name': message.document.file_name,
            'caption': message.caption or ""
        }
    elif message.photo:
        file_type = "photo"
        file_data = {
            'file_id': message.photo[-1].file_id,
            'caption': message.caption or ""
        }
    elif message.video:
        file_type = "video"
        file_data = {
            'file_id': message.video.file_id,
            'caption': message.caption or ""
        }
    elif message.audio:
        file_type = "audio"
        file_data = {
            'file_id': message.audio.file_id,
            'file_name': message.audio.file_name or "Аудио файл",
            'caption': message.caption or ""
        }
    elif message.voice:
        file_type = "voice"
        file_data = {
            'file_id': message.voice.file_id
        }
    elif message.video_note:
        file_type = "video_note"
        file_data = {
            'file_id': message.video_note.file_id
        }
    elif message.animation:
        file_type = "animation"
        file_data = {
            'file_id': message.animation.file_id,
            'caption': message.caption or ""
        }
    elif message.sticker:
        file_type = "sticker"
        file_data = {
            'file_id': message.sticker.file_id
        }
    
    # Если это файл (любой тип)
    if file_type:
        logging.info(f"Получен файл типа {file_type} от пользователя {message.from_user.id}")
        
        # Сохраняем файл и получаем уникальный код
        unique_code = save_file_info(file_data, file_type)
        
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
        
        # Отправляем сообщение с результатом
        await message.answer(
            f"✅ Файл успешно добавлен в базу!\n\n"
            f"🔗 Ссылка для получения: `{link}`\n\n"
            f"📊 Статистика:\n"
            f"• Тип файла: {file_type}\n"
            f"• Уникальный код: `{unique_code}`\n\n"
            f"ℹ️ Поделитесь ссылкой с другими пользователями",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Сбрасываем состояние
        await state.clear()
    else:
        # Если не файл, просим отправить файл
        await message.answer("Пожалуйста, отправьте файл (документ, фото, видео и т.д.)")
        return

# Обработчик команды /start с параметром
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logging.info(f"Команда /start от пользователя {user_id}, текст: {message.text}")
    
    # Проверяем, есть ли параметр в команде start
    if len(message.text.split()) > 1:
        code = message.text.split()[1]
        logging.info(f"Пользователь перешел по ссылке с кодом: {code}")
        
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
            logging.info(f"Найден файл с кодом {code}, тип: {file_info['file_type']}")
            try:
                file_data = file_info['file_data']
                
                # Отправляем файл в зависимости от типа
                if file_info['file_type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_data['file_id']
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_data['file_id']
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'sticker':
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_data['file_id']
                    )
                
                # Показываем статистику
                stats_text = (
                    f"✅ Файл успешно отправлен!\n\n"
                    f"📊 Статистика:\n"
                    f"• Использовано раз: {file_info['uses']}\n"
                    f"• Дата создания: {file_info['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🔗 Для нового файла используйте команду /addfile"
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
                logging.error(f"Ошибка при отправке файла: {e}")
                await message.answer(f"❌ Ошибка при отправке файла: {str(e)}")
        else:
            await message.answer("❌ Файл не найден или ссылка устарела.")
        return
    
    # Стандартная команда /start без параметра
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
        await state.set_state(FileUploadStates.waiting_for_subscription)

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
                file_data = file_info['file_data']
                chat_id = callback_query.message.chat.id
                
                # Отправляем файл в зависимости от типа
                if file_info['file_type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_data['file_id']
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_data['file_id']
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_data['file_id'],
                        caption=file_data.get('caption', '')
                    )
                elif file_info['file_type'] == 'sticker':
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_data['file_id']
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
    # Пропускаем если пользователь в состоянии ожидания файла
    current_state = await state.get_state()
    if current_state == FileUploadStates.waiting_for_file.state:
        return
    
    # Пропускаем если пользователь в состоянии ожидания подписки
    if current_state == FileUploadStates.waiting_for_subscription.state:
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
        await state.set_state(FileUploadStates.waiting_for_subscription)

# Команда для проверки статистики файлов (только для разрешенных пользователей)
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not is_user_allowed(user_id, username):
        return
    
    # Показываем статистику файлов
    total_files = len(file_storage)
    if total_files == 0:
        await message.answer("📊 В базе нет файлов.")
        return
    
    # Считаем использование
    total_uses = sum(file['uses'] for file in file_storage.values())
    
    # Формируем список файлов
    files_list = []
    for code, file_data in list(file_storage.items())[:10]:  # Первые 10 файлов
        files_list.append(
            f"• `{code}` - {file_data['file_type']} "
            f"(использовано: {file_data['uses']} раз)"
        )
    
    stats_text = (
        f"📊 Статистика базы файлов:\n\n"
        f"• Всего файлов: {total_files}\n"
        f"• Всего использований: {total_uses}\n\n"
        f"Последние файлы:\n" + "\n".join(files_list)
    )
    
    if total_files > 10:
        stats_text += f"\n\n... и еще {total_files - 10} файлов"
    
    await message.answer(stats_text, parse_mode=ParseMode.MARKDOWN)

# Основная функция
async def main():
    logging.info("Бот запускается...")
    logging.info(f"Разрешенные пользователи для /addfile: {ALLOWED_USERS}")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
