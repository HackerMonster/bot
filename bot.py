import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
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

# Разрешенные пользователи для команды /addfile и /ad
ALLOWED_USERS = [
    5870949629,  # ID пользователя
    "Feop06"     # Username пользователя
]

# ID чатов и каналов, где бот НЕ ДОЛЖЕН работать
BLACKLIST_CHAT_IDS = [-1002197945807, -1001621247413]

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера с хранилищем
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# Хранилище файлов (в памяти)
file_storage = {}

# Хранилище пользователей бота
user_storage = set()

# Состояния для создания рассылки
class BroadcastStates(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    preview_broadcast = State()

class FileUploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_subscription = State()

# Проверка доступа пользователя к команде /addfile и /ad
def is_user_allowed(user_id: int, username: str = None) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к команде /addfile и /ad
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

# Функция для сохранения пользователя
async def save_user(user_id: int):
    user_storage.add(user_id)

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

# Функция для создания клавиатуры с кнопками подписки (ТОЛЬКО КНОПКИ ПОДПИСКИ)
def create_subscription_keyboard_only():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="1️⃣ Подписаться — https://t.me/basegriefer", 
                    url="https://t.me/basegriefer"
                )
            ],
            [
                InlineKeyboardButton(
                    text="2️⃣ Подписаться - https://t.me/chatbasegriefer", 
                    url="https://t.me/chatbasegriefer"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data="check_subscription_main"
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
                    "❗ | Прежде чем пользоваться ботом",
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

# НОВАЯ КОМАНДА: /ad - рассылка всем пользователям
@dp.message(Command("ad"))
async def cmd_ad(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    logging.info(f"Команда /ad от пользователя {user_id} (@{username})")
    
    # Проверяем доступ пользователя
    if not is_user_allowed(user_id, username):
        logging.info(f"Пользователь {user_id} (@{username}) не имеет доступа к команде /ad")
        # Для остальных пользователей команда ничего не делает (не отвечает)
        return
    
    # У пользователя есть доступ
    await state.clear()  # Очищаем предыдущие состояния
    
    await message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте мне сообщение для рассылки. Можно отправить:\n"
        "• Текст\n"
        "• Фото с текстом\n"
        "• Видео с текстом\n"
        "• Документ с текстом\n"
        "• GIF с текстом\n\n"
        "После отправки контента вы сможете добавить кнопки.",
        parse_mode=ParseMode.HTML
    )
    
    await state.set_state(BroadcastStates.waiting_for_broadcast_content)

# Обработчик контента для рассылки
@dp.message(BroadcastStates.waiting_for_broadcast_content)
async def handle_broadcast_content(message: Message, state: FSMContext):
    # Сохраняем сообщение для рассылки
    broadcast_data = {
        'message_id': message.message_id,
        'chat_id': message.chat.id,
        'text': message.text or message.caption or "",
        'has_photo': bool(message.photo),
        'has_video': bool(message.video),
        'has_document': bool(message.document),
        'has_animation': bool(message.animation),
        'buttons': []  # Будем хранить кнопки здесь
    }
    
    # Сохраняем file_id если есть медиа
    if message.photo:
        broadcast_data['photo_file_id'] = message.photo[-1].file_id
    elif message.video:
        broadcast_data['video_file_id'] = message.video.file_id
    elif message.document:
        broadcast_data['document_file_id'] = message.document.file_id
    elif message.animation:
        broadcast_data['animation_file_id'] = message.animation.file_id
    
    await state.update_data(broadcast_data=broadcast_data)
    
    # Предлагаем добавить кнопку
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить кнопку",
                    callback_data="add_button"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁️ Посмотреть превью",
                    callback_data="preview_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Отправить рассылку",
                    callback_data="send_broadcast"
                )
            ]
        ]
    )
    
    await message.answer(
        "✅ Контент для рассылки сохранен!\n\n"
        "Теперь вы можете:\n"
        "1. Добавить кнопки к сообщению\n"
        "2. Посмотреть превью\n"
        "3. Отправить рассылку всем пользователям\n\n"
        "Используйте кнопки ниже:",
        reply_markup=keyboard
    )
    
    await state.set_state(BroadcastStates.preview_broadcast)

# Обработчик для добавления кнопки
@dp.callback_query(BroadcastStates.preview_broadcast, lambda c: c.data == "add_button")
async def add_button_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Введите текст для кнопки (например: 'Наш канал' или 'Перейти на сайт'):"
    )
    await state.set_state(BroadcastStates.waiting_for_button_text)
    await callback_query.answer()

# Обработчик текста кнопки
@dp.message(BroadcastStates.waiting_for_button_text)
async def handle_button_text(message: Message, state: FSMContext):
    button_text = message.text
    
    if len(button_text) > 64:
        await message.answer("❌ Текст кнопки слишком длинный (максимум 64 символа). Попробуйте снова:")
        return
    
    await state.update_data(button_text=button_text)
    await message.answer(
        f"Текст кнопки сохранен: <code>{button_text}</code>\n\n"
        "Теперь введите URL для кнопки (например: https://t.me/basegriefer):",
        parse_mode=ParseMode.HTML
    )
    
    await state.set_state(BroadcastStates.waiting_for_button_url)

# Обработчик URL кнопки
@dp.message(BroadcastStates.waiting_for_button_url)
async def handle_button_url(message: Message, state: FSMContext):
    button_url = message.text
    
    # Простая проверка URL
    if not button_url.startswith(('http://', 'https://', 'tg://')):
        await message.answer("❌ Неверный формат URL. URL должен начинаться с http://, https:// или tg://\nПопробуйте снова:")
        return
    
    # Получаем сохраненные данные
    state_data = await state.get_data()
    button_text = state_data.get('button_text')
    broadcast_data = state_data.get('broadcast_data')
    
    # Добавляем кнопку в список
    if 'buttons' not in broadcast_data:
        broadcast_data['buttons'] = []
    
    broadcast_data['buttons'].append({
        'text': button_text,
        'url': button_url
    })
    
    await state.update_data(broadcast_data=broadcast_data)
    
    # Создаем клавиатуру с текущими кнопками
    keyboard = create_broadcast_keyboard(broadcast_data['buttons'])
    
    await message.answer(
        f"✅ Кнопка добавлена!\n\n"
        f"<b>Текст:</b> {button_text}\n"
        f"<b>URL:</b> {button_url}\n\n"
        f"Всего кнопок: {len(broadcast_data['buttons'])}",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    
    # Возвращаем к меню управления рассылкой
    control_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить еще кнопку",
                    callback_data="add_button"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁️ Посмотреть превью",
                    callback_data="preview_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Отправить рассылку",
                    callback_data="send_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Очистить все кнопки",
                    callback_data="clear_buttons"
                )
            ]
        ]
    )
    
    await message.answer(
        "Что вы хотите сделать дальше?",
        reply_markup=control_keyboard
    )
    
    await state.set_state(BroadcastStates.preview_broadcast)

# Функция для создания клавиатуры рассылки
def create_broadcast_keyboard(buttons):
    keyboard_buttons = []
    
    for button in buttons:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button['text'],
                url=button['url']
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# Функция для создания клавиатуры управления рассылкой
def create_broadcast_control_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить кнопку",
                    callback_data="add_button"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👁️ Посмотреть превью",
                    callback_data="preview_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Отправить рассылку",
                    callback_data="send_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Очистить все кнопки",
                    callback_data="clear_buttons"
                )
            ]
        ]
    )

# Обработчик для просмотра превью
@dp.callback_query(BroadcastStates.preview_broadcast, lambda c: c.data == "preview_broadcast")
async def preview_broadcast_callback(callback_query: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    broadcast_data = state_data.get('broadcast_data')
    
    if not broadcast_data:
        await callback_query.answer("❌ Нет данных для превью", show_alert=True)
        return
    
    # Создаем клавиатуру с кнопками
    keyboard = create_broadcast_keyboard(broadcast_data.get('buttons', []))
    
    try:
        # Отправляем превью
        if broadcast_data.get('has_photo'):
            await bot.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=broadcast_data['photo_file_id'],
                caption=broadcast_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif broadcast_data.get('has_video'):
            await bot.send_video(
                chat_id=callback_query.message.chat.id,
                video=broadcast_data['video_file_id'],
                caption=broadcast_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif broadcast_data.get('has_document'):
            await bot.send_document(
                chat_id=callback_query.message.chat.id,
                document=broadcast_data['document_file_id'],
                caption=broadcast_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        elif broadcast_data.get('has_animation'):
            await bot.send_animation(
                chat_id=callback_query.message.chat.id,
                animation=broadcast_data['animation_file_id'],
                caption=broadcast_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        else:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=broadcast_data['text'],
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        
        await callback_query.answer("✅ Превью отправлено")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке превью: {e}")
        await callback_query.answer("❌ Ошибка при отправке превью", show_alert=True)

# Обработчик для отправки рассылки
@dp.callback_query(BroadcastStates.preview_broadcast, lambda c: c.data == "send_broadcast")
async def send_broadcast_callback(callback_query: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    broadcast_data = state_data.get('broadcast_data')
    
    if not broadcast_data:
        await callback_query.answer("❌ Нет данных для рассылки", show_alert=True)
        return
    
    await callback_query.message.edit_text(
        "🚀 <b>Начинаю рассылку...</b>\n\n"
        f"Всего пользователей: {len(user_storage)}\n"
        "Рассылка может занять некоторое время...",
        parse_mode=ParseMode.HTML
    )
    
    # Создаем клавиатуру с кнопками
    keyboard = create_broadcast_keyboard(broadcast_data.get('buttons', []))
    
    success_count = 0
    fail_count = 0
    total_users = len(user_storage)
    
    # Отправляем всем пользователям
    for user_id in user_storage:
        try:
            if broadcast_data.get('has_photo'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=broadcast_data['photo_file_id'],
                    caption=broadcast_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            elif broadcast_data.get('has_video'):
                await bot.send_video(
                    chat_id=user_id,
                    video=broadcast_data['video_file_id'],
                    caption=broadcast_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            elif broadcast_data.get('has_document'):
                await bot.send_document(
                    chat_id=user_id,
                    document=broadcast_data['document_file_id'],
                    caption=broadcast_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            elif broadcast_data.get('has_animation'):
                await bot.send_animation(
                    chat_id=user_id,
                    animation=broadcast_data['animation_file_id'],
                    caption=broadcast_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=broadcast_data['text'],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
            
            success_count += 1
            await asyncio.sleep(0.05)  # Задержка чтобы не превысить лимиты
            
            # Обновляем статус каждые 50 отправок
            if success_count % 50 == 0:
                await callback_query.message.edit_text(
                    f"🚀 <b>Рассылка в процессе...</b>\n\n"
                    f"Успешно отправлено: {success_count}/{total_users}\n"
                    f"Не удалось: {fail_count}",
                    parse_mode=ParseMode.HTML
                )
                
        except Exception as e:
            logging.error(f"Ошибка при отправке пользователю {user_id}: {e}")
            fail_count += 1
    
    # Финальное сообщение
    await callback_query.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 Статистика:\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Успешно отправлено: {success_count}\n"
        f"• Не удалось отправить: {fail_count}\n\n"
        f"Процент успеха: {round(success_count/total_users*100 if total_users > 0 else 0, 2)}%",
        parse_mode=ParseMode.HTML
    )
    
    # Очищаем состояние
    await state.clear()
    await callback_query.answer()

# Обработчик для очистки кнопок
@dp.callback_query(BroadcastStates.preview_broadcast, lambda c: c.data == "clear_buttons")
async def clear_buttons_callback(callback_query: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    broadcast_data = state_data.get('broadcast_data')
    
    if broadcast_data:
        broadcast_data['buttons'] = []
        await state.update_data(broadcast_data=broadcast_data)
    
    await callback_query.message.edit_text(
        "✅ Все кнопки очищены!\n\n"
        "Что вы хотите сделать дальше?",
        reply_markup=create_broadcast_control_keyboard()
    )
    await callback_query.answer("✅ Кнопки очищены")

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
        
        # Создаем клавиатуру только с кнопкой канала
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
        
        # Отправляем сообщение о успешной загрузке со ссылкой в тексте
        await message.answer(
            f"<b>Файл успешно загружен ❗</b>\n\n"
            f"<b>Ссылка 👇</b>\n"
            f"<code>{link}</code>\n\n"
            f"ℹ️ Нажмите на ссылку выше, чтобы скопировать её",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
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
    
    # Сохраняем пользователя в базу для рассылок
    await save_user(user_id)
    
    logging.info(f"Команда /start от пользователя {user_id}, текст: {message.text}")
    
    # Проверяем, есть ли параметр в команде start
    if len(message.text.split()) > 1:
        code = message.text.split()[1]
        logging.info(f"Пользователь перешел по ссылке с кодом: {code}")
        
        # Проверяем подписку перед выдачей файла
        subscription_status = await check_user_subscription(user_id)
        
        if subscription_status["subscribed_count"] < subscription_status["total_count"]:
            # ИСПРАВЛЕННЫЙ ТЕКСТ: НЕ показывает сообщение с подпиской
            # Вместо этого просто показываем стандартное приветствие с требованием подписки
            
            # Удаляем старые сообщения о подписке
            await delete_all_subscription_messages(chat_id)
            
            # Показываем стандартное требование подписки
            warning_text = "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!"
            
            # Используем клавиатуру только с кнопками подписки
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="1️⃣ Подписаться — https://t.me/basegriefer", 
                            url="https://t.me/basegriefer"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="2️⃣ Подписаться - https://t.me/chatbasegriefer", 
                            url="https://t.me/chatbasegriefer"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="✅ Проверить подписку",
                            callback_data="check_subscription_main"
                        )
                    ]
                ]
            )
            
            sent_message = await message.answer(warning_text, reply_markup=keyboard)
            await state.update_data(last_subscription_message_id=sent_message.message_id)
            await state.set_state(FileUploadStates.waiting_for_subscription)
            return
        
        # Если подписан - отправляем файл
        file_info = get_file_by_code(code)
        if file_info:
            logging.info(f"Найден файл с кодом {code}, тип: {file_info['file_type']}")
            try:
                file_data = file_info['file_data']
                
                # Создаем кнопку для файла
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Наш канал 👾",
                                url="https://t.me/basegriefer"
                            )
                        ]
                    ]
                )
                
                # Отправляем файл с кнопкой
                if file_info['file_type'] == 'document':
                    await bot.send_document(
                        chat_id=chat_id,
                        document=file_data['file_id'],
                        caption=file_data.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_data['file_id'],
                        caption=file_data.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_data['file_id'],
                        caption=file_data.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_data['file_id'],
                        caption=file_data.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_data['file_id'],
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_data['file_id'],
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_data['file_id'],
                        caption=file_data.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'sticker':
                    # Для стикеров сначала отправляем стикер, потом кнопку отдельно
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_data['file_id']
                    )
                    await message.answer("Ваш стикер", reply_markup=keyboard)
                
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
        
        # ТЕКСТ С ТРЕБОВАНИЕМ ПОДПИСКИ
        warning_text = "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!"
        
        # Клавиатура только с кнопками подписки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="1️⃣ Подписаться — https://t.me/basegriefer", 
                        url="https://t.me/basegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="2️⃣ Подписаться - https://t.me/chatbasegriefer", 
                        url="https://t.me/chatbasegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Проверить подписку",
                        callback_data="check_subscription_main"
                    )
                ]
            ]
        )
        
        sent_message = await message.answer(warning_text, reply_markup=keyboard)
        await state.update_data(last_subscription_message_id=sent_message.message_id)
        await state.set_state(FileUploadStates.waiting_for_subscription)

# Обработчик для кнопки "Проверить подписку" (основная)
@dp.callback_query(lambda c: c.data == "check_subscription_main")
async def check_subscription_main_callback(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] == subscription_status["total_count"]:
        # Пользователь подписан
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
        
        # Удаляем старое сообщение о подписке
        try:
            await callback_query.message.delete()
        except Exception as e:
            logging.error(f"Не удалось удалить старое сообщение: {e}")
            
    else:
        # Пользователь все еще не подписан
        warning_text = (
            f"⚠️ Подпишитесь на все каналы.\n"
            f"❌ Подтверждено: {subscription_status['subscribed_count']} из {subscription_status['total_count']}.\n\n"
            "❗ Нажмите по кнопкам выше, затем проверьте подписку."
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="1️⃣ Подписаться — https://t.me/basegriefer", 
                        url="https://t.me/basegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="2️⃣ Подписаться - https://t.me/chatbasegriefer", 
                        url="https://t.me/chatbasegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Проверить подписку",
                        callback_data="check_subscription_main"
                    )
                ]
            ]
        )
        
        await callback_query.message.edit_text(warning_text, reply_markup=keyboard)
    
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
    
    # Пропускаем если пользователь в состоянии создания рассылки
    if current_state in [BroadcastStates.waiting_for_broadcast_content.state,
                        BroadcastStates.waiting_for_button_text.state,
                        BroadcastStates.waiting_for_button_url.state,
                        BroadcastStates.preview_broadcast.state]:
        return
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    subscription_status = await check_user_subscription(user_id)
    
    if subscription_status["subscribed_count"] < subscription_status["total_count"]:
        await delete_all_subscription_messages(chat_id)
        
        # ТЕКСТ С ТРЕБОВАНИЕМ ПОДПИСКИ
        warning_text = "❗ | Прежде чем пользоваться ботом, подпишись на указанные каналы ниже!"
        
        # Клавиатура только с кнопками подписки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="1️⃣ Подписаться — https://t.me/basegriefer", 
                        url="https://t.me/basegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="2️⃣ Подписаться - https://t.me/chatbasegriefer", 
                        url="https://t.me/chatbasegriefer"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Проверить подписку",
                        callback_data="check_subscription_main"
                    )
                ]
            ]
        )
        
        sent_message = await message.answer(warning_text, reply_markup=keyboard)
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

# Команда для проверки статистики пользователей (только для разрешенных пользователей)
@dp.message(Command("users"))
async def cmd_users(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not is_user_allowed(user_id, username):
        return
    
    total_users = len(user_storage)
    
    stats_text = (
        f"👥 <b>Статистика пользователей</b>\n\n"
        f"• Всего пользователей бота: {total_users}\n"
        f"• Последние 10 пользователей:\n"
    )
    
    # Показываем последних 10 пользователей (если есть)
    if total_users > 0:
        users_list = list(user_storage)
        last_users = users_list[-10:] if total_users > 10 else users_list
        
        for i, user_id in enumerate(last_users, 1):
            try:
                user = await bot.get_chat(user_id)
                username_display = f"@{user.username}" if user.username else "без username"
                stats_text += f"{i}. {user.first_name} ({username_display}) - ID: {user_id}\n"
            except Exception as e:
                stats_text += f"{i}. ID: {user_id} (недоступен)\n"
    
    await message.answer(stats_text, parse_mode=ParseMode.HTML)

# Основная функция
async def main():
    logging.info("Бот запускается...")
    logging.info(f"Разрешенные пользователи для /addfile и /ad: {ALLOWED_USERS}")
    logging.info(f"Текущее количество пользователей: {len(user_storage)}")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
