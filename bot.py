import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import uuid
from datetime import datetime, timedelta
from contextlib import closing

# Токен бота
API_TOKEN = '8323926582:AAF0Nzg0HdhF0_4WrlaOonBA4bLokSJxWWU'

# ID каналов для проверки подписки
CHANNELS = [
    {"name": "BaseGriefer", "url": "https://t.me/basegriefer", "username": "basegriefer"},
    {"name": "Chat BaseGriefer", "url": "https://t.me/chatbasegriefer", "username": "chatbasegriefer"}
]

# Разработчик (владелец бота)
DEVELOPER_ID = 5870949629  # ID разработчика

# Уровни доступа:
# 1 - Рассылка
# 2 - Загрузка файлов
# 3 - Просмотр файлов
# 4 - Статистика
# 5 - Владелец (всё)
# 6 - Второй владелец (всё)

# ID чатов и каналов, где бот НЕ ДОЛЖЕН работать
BLACKLIST_CHAT_IDS = [-1002197945807, -1001621247413]

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера с хранилищем
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# ========== БАЗА ДАННЫХ SQLite ==========
DB_NAME = "bot_database.db"

# Функция для инициализации базы данных
def init_database():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_admin INTEGER DEFAULT 0,
            admin_level INTEGER DEFAULT 0,
            subscribed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            downloads INTEGER DEFAULT 0
        )
        ''')
        
        # Таблица файлов
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            file_id TEXT PRIMARY KEY,
            file_type TEXT NOT NULL,
            telegram_file_id TEXT NOT NULL,
            file_name TEXT,
            caption TEXT,
            uses INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (user_id)
        )
        ''')
        
        # Таблица статистики загрузок
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            file_id TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (file_id) REFERENCES files (file_id)
        )
        ''')
        
        # Таблица администраторов
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_user_id ON users (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users (is_admin)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_file_id ON files (file_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_files_created_by ON files (created_by)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_stats_date ON download_stats (downloaded_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_admins_level ON admins (level)')
        
        # Добавляем разработчика как владельца (уровень 5)
        cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (DEVELOPER_ID,))
        if not cursor.fetchone():
            cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (DEVELOPER_ID,))
            cursor.execute('INSERT INTO admins (user_id, level, added_by) VALUES (?, 5, ?)', (DEVELOPER_ID, DEVELOPER_ID))
            cursor.execute('UPDATE users SET is_admin = 1, admin_level = 5 WHERE user_id = ?', (DEVELOPER_ID,))
        
        conn.commit()
        logging.info("База данных инициализирована")

# Функция для проверки прав администратора
def check_admin_access(user_id: int, required_level: int = 1) -> bool:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT admin_level FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result and result[0] >= required_level:
            return True
        return False

# Функция для получения уровня администратора
def get_admin_level(user_id: int) -> int:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT admin_level FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

# Функция для сохранения пользователя
def save_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            # Обновляем информацию о пользователе
            cursor.execute('''
            UPDATE users 
            SET username = ?, first_name = ?, last_name = ?, last_activity = CURRENT_TIMESTAMP
            WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
        else:
            # Добавляем нового пользователя
            cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, created_at, last_activity)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (user_id, username, first_name, last_name))
        
        conn.commit()

# Функция для получения всех пользователей для рассылки
def get_all_users():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        return [user[0] for user in users]

# Функция для получения количества пользователей
def get_users_count():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

# Функция для получения активных пользователей (последние 7 дней)
def get_active_users_count(days: int = 7):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT COUNT(DISTINCT user_id) 
        FROM download_stats 
        WHERE downloaded_at >= datetime('now', ?)
        ''', (f'-{days} days',))
        return cursor.fetchone()[0]

# Функция для сохранения файла в базу данных
def save_file_to_db(file_data: dict, file_type: str, created_by: int):
    file_id = str(uuid.uuid4())[:12]
    
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO files (file_id, file_type, telegram_file_id, file_name, caption, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            file_id,
            file_type,
            file_data['file_id'],
            file_data.get('file_name', ''),
            file_data.get('caption', ''),
            created_by
        ))
        
        conn.commit()
    
    logging.info(f"Файл сохранен в БД с ID: {file_id}, тип: {file_type}")
    return file_id

# Функция для получения файла из базы данных
def get_file_from_db(file_id: str, user_id: int = None):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT file_type, telegram_file_id, file_name, caption, uses, created_at, created_by
        FROM files WHERE file_id = ?
        ''', (file_id,))
        result = cursor.fetchone()
        
        if result:
            # Увеличиваем счетчик использований
            cursor.execute('UPDATE files SET uses = uses + 1 WHERE file_id = ?', (file_id,))
            
            # Записываем статистику загрузки
            if user_id:
                cursor.execute('''
                INSERT INTO download_stats (user_id, file_id) VALUES (?, ?)
                ''', (user_id, file_id))
                
                # Увеличиваем счетчик загрузок пользователя
                cursor.execute('''
                UPDATE users SET downloads = downloads + 1 WHERE user_id = ?
                ''', (user_id,))
            
            conn.commit()
            
            return {
                'file_type': result[0],
                'telegram_file_id': result[1],
                'file_name': result[2],
                'caption': result[3] or '',
                'uses': result[4] + 1,  # +1 потому что только что увеличили
                'created_at': result[5],
                'created_by': result[6]
            }
        return None

# Функция для получения списка файлов
def get_files_list(limit: int = 20, offset: int = 0):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT f.file_id, f.file_type, f.file_name, f.uses, f.created_at, 
               u.username, u.user_id
        FROM files f
        LEFT JOIN users u ON f.created_by = u.user_id
        ORDER BY f.created_at DESC
        LIMIT ? OFFSET ?
        ''', (limit, offset))
        return cursor.fetchall()

# Функция для получения общего количества файлов
def get_files_count():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM files')
        return cursor.fetchone()[0]

# Функция для удаления файла
def delete_file(file_id: str, deleted_by: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Получаем информацию о файле перед удалением
        cursor.execute('SELECT telegram_file_id, created_by FROM files WHERE file_id = ?', (file_id,))
        file_info = cursor.fetchone()
        
        if file_info:
            # Удаляем файл
            cursor.execute('DELETE FROM files WHERE file_id = ?', (file_id,))
            # Удаляем статистику загрузок этого файла
            cursor.execute('DELETE FROM download_stats WHERE file_id = ?', (file_id,))
            
            conn.commit()
            return True, file_info[1]  # Возвращаем ID создателя файла
        return False, None

# Функция для получения статистики загрузок
def get_download_stats():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Сегодняшние загрузки
        cursor.execute('''
        SELECT COUNT(*) FROM download_stats 
        WHERE DATE(downloaded_at) = DATE('now')
        ''')
        today_downloads = cursor.fetchone()[0]
        
        # Вчерашние загрузки
        cursor.execute('''
        SELECT COUNT(*) FROM download_stats 
        WHERE DATE(downloaded_at) = DATE('now', '-1 day')
        ''')
        yesterday_downloads = cursor.fetchone()[0]
        
        # Всего загрузок
        cursor.execute('SELECT COUNT(*) FROM download_stats')
        total_downloads = cursor.fetchone()[0]
        
        # Загрузок за последние 7 дней
        cursor.execute('''
        SELECT COUNT(*) FROM download_stats 
        WHERE downloaded_at >= datetime('now', '-7 days')
        ''')
        week_downloads = cursor.fetchone()[0]
        
        # Количество загруженных файлов
        total_files = get_files_count()
        
        # Самые популярные файлы
        cursor.execute('''
        SELECT f.file_name, f.uses, f.file_id
        FROM files f
        ORDER BY f.uses DESC
        LIMIT 5
        ''')
        top_files = cursor.fetchall()
        
        return {
            'today': today_downloads,
            'yesterday': yesterday_downloads,
            'total': total_downloads,
            'week': week_downloads,
            'total_files': total_files,
            'top_files': top_files
        }

# Функция для добавления администратора
def add_admin(user_id: int, level: int, added_by: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            # Добавляем пользователя если не существует
            cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        
        # Добавляем/обновляем администратора
        cursor.execute('''
        INSERT OR REPLACE INTO admins (user_id, level, added_by, added_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, level, added_by))
        
        # Обновляем статус в таблице users
        cursor.execute('''
        UPDATE users SET is_admin = 1, admin_level = ? WHERE user_id = ?
        ''', (level, user_id))
        
        conn.commit()
        return True

# Функция для удаления администратора
def remove_admin(user_id: int, removed_by: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        
        # Удаляем из таблицы admins
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        
        # Обновляем статус в таблице users
        cursor.execute('UPDATE users SET is_admin = 0, admin_level = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        return True

# Функция для получения списка администраторов
def get_admins_list():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT u.user_id, u.username, u.first_name, a.level, a.added_at
        FROM admins a
        JOIN users u ON a.user_id = u.user_id
        ORDER BY a.level DESC
        ''')
        return cursor.fetchall()

# Функция для проверки, является ли пользователь администратором
def is_admin(user_id: int):
    return check_admin_access(user_id, 1)

# Состояния для создания рассылки
class BroadcastStates(StatesGroup):
    waiting_for_broadcast_content = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    preview_broadcast = State()

class FileUploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_subscription = State()

class AdminStates(StatesGroup):
    waiting_for_admin_username = State()
    waiting_for_admin_level = State()
    waiting_for_remove_admin = State()
    waiting_for_remove_reason = State()

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

# Функция для создания клавиатуры с кнопкой отмены
def create_cancel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_operation"
                )
            ]
        ]
    )

# Функция для создания клавиатуры подтверждения
def create_confirm_keyboard(action: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_{action}"
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_operation"
                )
            ]
        ]
    )

# Функция для создания клавиатуры назад
def create_back_keyboard(back_to: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"back_{back_to}"
                )
            ]
        ]
    )

# ========== КОМАНДЫ АДМИНИСТРАТОРА ==========

# Команда /addadmin
@dp.message(Command("addadmin"))
async def cmd_addadmin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь владельцем (уровень 5 или 6)
    if not check_admin_access(user_id, 5):
        await message.answer("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    # Парсим аргументы
    args = message.text.split()
    if len(args) != 3:
        await message.answer(
            "📝 <b>Использование команды:</b>\n"
            "<code>/addadmin [юзер] [уровень]</code>\n\n"
            "📊 <b>Уровни доступа:</b>\n"
            "1️⃣ — Рассылка\n"
            "2️⃣ — Загрузка файлов\n"
            "3️⃣ — Просмотр файлов\n"
            "4️⃣ — Статистика\n"
            "5️⃣ — Владелец (всё)\n"
            "6️⃣ — Второй владелец (всё)\n\n"
            "⚠️ <b>Внимание:</b> Только владелец может добавлять администраторов!",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = args[1].replace('@', '')  # Убираем @ если есть
    try:
        level = int(args[2])
        if level < 1 or level > 6:
            raise ValueError
    except ValueError:
        await message.answer("❌ Уровень должен быть числом от 1 до 6.")
        return
    
    # Сохраняем данные в состоянии
    await state.update_data(username=username, level=level)
    
    # Запрашиваем подтверждение
    await message.answer(
        f"⚠️ <b>Подтвердите добавление администратора</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"📊 <b>Уровень доступа:</b> {level}\n"
        f"👑 <b>Добавляет:</b> {message.from_user.first_name}\n\n"
        f"<i>После подтверждения пользователю будет отправлено уведомление.</i>",
        reply_markup=create_confirm_keyboard("add_admin"),
        parse_mode=ParseMode.HTML
    )

# Команда /admin-panel
@dp.message(Command("admin-panel"))
async def cmd_admin_panel(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not is_admin(user_id):
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    level = get_admin_level(user_id)
    
    # Создаем клавиатуру в зависимости от уровня доступа
    keyboard_buttons = []
    
    if level >= 1:  # Рассылка
        keyboard_buttons.append([
            InlineKeyboardButton(text="📢 Создать рассылку", callback_data="admin_broadcast")
        ])
    
    if level >= 2:  # Загрузка файлов
        keyboard_buttons.append([
            InlineKeyboardButton(text="📁 Загрузить файл", callback_data="admin_upload_file")
        ])
    
    if level >= 3:  # Просмотр файлов
        keyboard_buttons.append([
            InlineKeyboardButton(text="📋 Список файлов", callback_data="admin_files_list")
        ])
    
    if level >= 4:  # Статистика
        keyboard_buttons.append([
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ])
    
    if level >= 5:  # Управление администраторами
        keyboard_buttons.append([
            InlineKeyboardButton(text="👑 Список админов", callback_data="admin_list_admins")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_admin"),
            InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove_admin")
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"👑 <b>Админ-панель</b>\n\n"
        f"👤 <b>Вы:</b> {message.from_user.first_name}\n"
        f"📊 <b>Уровень доступа:</b> {level}\n\n"
        f"<i>Выберите действие:</i>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

# Команда /offadmin
@dp.message(Command("offadmin"))
async def cmd_offadmin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь владельцем (уровень 5 или 6)
    if not check_admin_access(user_id, 5):
        await message.answer("❌ Только владелец может снимать администраторов.")
        return
    
    # Парсим аргументы
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "📝 <b>Использование команды:</b>\n"
            "<code>/offadmin [юзер] [причина]</code>\n\n"
            "⚠️ <b>Внимание:</b> Только владелец может снимать администраторов!",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = args[1].replace('@', '')  # Убираем @ если есть
    reason = ' '.join(args[2:]) if len(args) > 2 else "Причина не указана"
    
    # Сохраняем данные в состоянии
    await state.update_data(username=username, reason=reason)
    
    # Запрашиваем подтверждение
    await message.answer(
        f"⚠️ <b>Подтвердите снятие администратора</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"📝 <b>Причина:</b> {reason}\n"
        f"👑 <b>Снимает:</b> {message.from_user.first_name}\n\n"
        f"<i>После подтверждения пользователю будет отправлено уведомление.</i>",
        reply_markup=create_confirm_keyboard("remove_admin"),
        parse_mode=ParseMode.HTML
    )

# Команда /files
@dp.message(Command("files"))
async def cmd_files(message: Message):
    user_id = message.from_user.id
    
    # Проверяем права доступа (уровень 3 или выше)
    if not check_admin_access(user_id, 3):
        await message.answer("❌ У вас нет прав для просмотра списка файлов.")
        return
    
    # Получаем список файлов
    files = get_files_list(limit=10)
    
    if not files:
        await message.answer("📭 В базе данных нет файлов.")
        return
    
    # Формируем сообщение
    files_text = "📋 <b>Список файлов</b>\n\n"
    
    for i, file in enumerate(files, 1):
        file_id, file_type, file_name, uses, created_at, username, created_by = file
        username_display = f"@{username}" if username else f"ID: {created_by}"
        
        # Обрезаем длинные имена файлов
        if file_name and len(file_name) > 30:
            file_name = file_name[:27] + "..."
        
        files_text += (
            f"<b>{i}. {file_name or 'Без имени'}</b>\n"
            f"   └ <code>{file_id}</code>\n"
            f"   └ Тип: {file_type} | 📥: {uses}\n"
            f"   └ Добавил: {username_display}\n\n"
        )
    
    # Создаем клавиатуру для навигации
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin_panel"),
                InlineKeyboardButton(text="🗑️ Удалить файл", callback_data="files_delete")
            ],
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="files_refresh")
            ]
        ]
    )
    
    await message.answer(files_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# Команда /stats
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    
    # Проверяем права доступа (уровень 4 или выше)
    if not check_admin_access(user_id, 4):
        await message.answer("❌ У вас нет прав для просмотра статистики.")
        return
    
    # Получаем статистику
    stats = get_download_stats()
    users_count = get_users_count()
    active_users = get_active_users_count(7)
    
    # Формируем красивое сообщение
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        
        "👥 <b>Пользователи:</b>\n"
        f"   ├ Всего: <b>{users_count}</b>\n"
        f"   └ Активных (7 дней): <b>{active_users}</b>\n\n"
        
        "📈 <b>Загрузки:</b>\n"
        f"   ├ Сегодня: <b>{stats['today']}</b>\n"
        f"   ├ Вчера: <b>{stats['yesterday']}</b>\n"
        f"   ├ За неделю: <b>{stats['week']}</b>\n"
        f"   └ Всего: <b>{stats['total']}</b>\n\n"
        
        "📁 <b>Файлы:</b>\n"
        f"   └ Всего загружено: <b>{stats['total_files']}</b>\n\n"
    )
    
    # Добавляем топ файлов если они есть
    if stats['top_files']:
        stats_text += "🏆 <b>Топ-5 файлов:</b>\n"
        for i, (file_name, uses, file_id) in enumerate(stats['top_files'], 1):
            if file_name and len(file_name) > 20:
                file_name = file_name[:17] + "..."
            stats_text += f"{i}. {file_name or 'Без имени'} — 📥 {uses}\n"
    
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin_panel"),
                InlineKeyboardButton(text="🔄 Обновить", callback_data="stats_refresh")
            ]
        ]
    )
    
    await message.answer(stats_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# ========== ОБРАБОТЧИКИ CALLBACK-КНОПОК ==========

# Обработчик для кнопки отмены
@dp.callback_query(lambda c: c.data == "cancel_operation")
async def cancel_operation_callback(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("❌ Операция отменена.")
    await callback_query.answer("✅ Операция отменена")

# Обработчик для кнопки назад
@dp.callback_query(lambda c: c.data.startswith("back_"))
async def back_callback(callback_query: CallbackQuery, state: FSMContext):
    action = callback_query.data.replace("back_", "")
    
    if action == "admin_panel":
        await cmd_admin_panel(callback_query.message)
    elif action == "files_list":
        await cmd_files(callback_query.message)
    elif action == "stats":
        await cmd_stats(callback_query.message)
    
    await callback_query.answer()

# Обработчик для подтверждения добавления администратора
@dp.callback_query(lambda c: c.data == "confirm_add_admin")
async def confirm_add_admin_callback(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    username = data.get('username')
    level = data.get('level')
    added_by = callback_query.from_user.id
    
    try:
        # Получаем ID пользователя по username
        user = await bot.get_chat(f"@{username}")
        user_id = user.id
        
        # Добавляем администратора
        add_admin(user_id, level, added_by)
        
        # Отправляем уведомление новому администратору
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Вы были добавлены в администрацию бота!\n"
                f"📊 <b>Ваш уровень:</b> {level}\n\n"
                f"<i>Используйте команду /admin-panel для доступа к админ-панели.</i>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        await callback_query.message.edit_text(
            f"✅ <b>Администратор успешно добавлен!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{username}\n"
            f"📊 <b>Уровень:</b> {level}\n"
            f"👑 <b>Добавил:</b> {callback_query.from_user.first_name}\n\n"
            f"<i>Пользователь получил уведомление.</i>",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logging.error(f"Ошибка при добавлении администратора: {e}")
        await callback_query.message.edit_text(
            f"❌ <b>Ошибка при добавлении администратора</b>\n\n"
            f"Пользователь @{username} не найден или произошла ошибка.\n"
            f"<i>Проверьте правильность username.</i>",
            parse_mode=ParseMode.HTML
        )
    
    await state.clear()
    await callback_query.answer()

# Обработчик для подтверждения удаления администратора
@dp.callback_query(lambda c: c.data == "confirm_remove_admin")
async def confirm_remove_admin_callback(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    username = data.get('username')
    reason = data.get('reason')
    removed_by = callback_query.from_user.id
    
    try:
        # Получаем ID пользователя по username
        user = await bot.get_chat(f"@{username}")
        user_id = user.id
        
        # Удаляем администратора
        remove_admin(user_id, removed_by)
        
        # Отправляем уведомление снятому администратору
        try:
            await bot.send_message(
                user_id,
                f"⚠️ <b>Уведомление</b>\n\n"
                f"Вы были сняты с админки ❗\n"
                f"📝 <b>Причина:</b> {reason}\n\n"
                f"<i>Если это ошибка, свяжитесь с владельцем бота.</i>",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        await callback_query.message.edit_text(
            f"✅ <b>Администратор успешно снят!</b>\n\n"
            f"👤 <b>Пользователь:</b> @{username}\n"
            f"📝 <b>Причина:</b> {reason}\n"
            f"👑 <b>Снял:</b> {callback_query.from_user.first_name}\n\n"
            f"<i>Пользователь получил уведомление.</i>",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logging.error(f"Ошибка при снятии администратора: {e}")
        await callback_query.message.edit_text(
            f"❌ <b>Ошибка при снятии администратора</b>\n\n"
            f"Пользователь @{username} не найден или произошла ошибка.\n"
            f"<i>Проверьте правильность username.</i>",
            parse_mode=ParseMode.HTML
        )
    
    await state.clear()
    await callback_query.answer()

# Обработчик для админ-панели кнопок
@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def admin_panel_callback(callback_query: CallbackQuery):
    action = callback_query.data.replace("admin_", "")
    
    if action == "broadcast":
        await cmd_ad(callback_query.message)
    elif action == "upload_file":
        await cmd_addfile(callback_query.message)
    elif action == "files_list":
        await cmd_files(callback_query.message)
    elif action == "stats":
        await cmd_stats(callback_query.message)
    elif action == "list_admins":
        await show_admins_list(callback_query.message)
    elif action == "add_admin":
        await callback_query.message.answer("Введите команду: /addadmin [юзер] [уровень]")
    elif action == "remove_admin":
        await callback_query.message.answer("Введите команду: /offadmin [юзер] [причина]")
    
    await callback_query.answer()

# Функция для показа списка администраторов
async def show_admins_list(message: Message):
    admins = get_admins_list()
    
    if not admins:
        await message.answer("👑 <b>Список администраторов пуст</b>", parse_mode=ParseMode.HTML)
        return
    
    admins_text = "👑 <b>Список администраторов</b>\n\n"
    
    for i, admin in enumerate(admins, 1):
        user_id, username, first_name, level, added_at = admin
        username_display = f"@{username}" if username else f"ID: {user_id}"
        name_display = first_name or "Без имени"
        
        # Описание уровня
        level_desc = {
            1: "Рассылка",
            2: "Загрузка файлов",
            3: "Просмотр файлов",
            4: "Статистика",
            5: "Владелец",
            6: "Второй владелец"
        }.get(level, "Неизвестно")
        
        admins_text += (
            f"<b>{i}. {name_display}</b> ({username_display})\n"
            f"   └ Уровень: {level} ({level_desc})\n"
            f"   └ Добавлен: {added_at[:10]}\n\n"
        )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_admin_panel")
            ]
        ]
    )
    
    await message.answer(admins_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# Обработчик для обновления статистики
@dp.callback_query(lambda c: c.data == "stats_refresh")
async def stats_refresh_callback(callback_query: CallbackQuery):
    await cmd_stats(callback_query.message)
    await callback_query.answer("🔄 Статистика обновлена")

# Обработчик для обновления списка файлов
@dp.callback_query(lambda c: c.data == "files_refresh")
async def files_refresh_callback(callback_query: CallbackQuery):
    await cmd_files(callback_query.message)
    await callback_query.answer("🔄 Список файлов обновлен")

# ========== СУЩЕСТВУЮЩИЕ ФУНКЦИИ (с проверкой прав) ==========

# НОВАЯ КОМАНДА: /ad - рассылка всем пользователям
@dp.message(Command("ad"))
async def cmd_ad(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем права доступа (уровень 1 или выше)
    if not check_admin_access(user_id, 1):
        await message.answer("❌ У вас нет прав для создания рассылки.")
        return
    
    # У пользователя есть доступ
    await state.clear()  # Очищаем предыдущие состояния
    
    keyboard = create_cancel_keyboard()
    
    await message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте мне сообщение для рассылки. Можно отправить:\n"
        "• Текст\n"
        "• Фото с текстом\n"
        "• Видео с текстом\n"
        "• Документ с текстом\n"
        "• GIF с текстом\n\n"
        "После отправки контента вы сможете добавить кнопки.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    
    await state.set_state(BroadcastStates.waiting_for_broadcast_content)

# НОВАЯ КОМАНДА: /addfile - загрузка файлов
@dp.message(Command("addfile"))
async def cmd_addfile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем права доступа (уровень 2 или выше)
    if not check_admin_access(user_id, 2):
        await message.answer("❌ У вас нет прав для загрузки файлов.")
        return
    
    keyboard = create_cancel_keyboard()
    
    await message.answer(
        "📤 <b>Загрузка файла</b>\n\n"
        "Отправьте файл, который хотите добавить в базу.\n"
        "Можно отправить:\n"
        "• Документ\n• Фото\n• Видео\n• Аудио\n• Голосовое сообщение\n• GIF\n• Стикер",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(FileUploadStates.waiting_for_file)

# Обработчик получения файла после команды /addfile
@dp.message(FileUploadStates.waiting_for_file)
async def handle_file_upload(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем права доступа (уровень 2 или выше)
    if not check_admin_access(user_id, 2):
        await message.answer("❌ У вас нет прав для загрузки файлов.")
        await state.clear()
        return
    
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
        logging.info(f"Получен файл типа {file_type} от пользователя {user_id}")
        
        # Сохраняем файл в базу данных и получаем уникальный код
        unique_code = save_file_to_db(file_data, file_type, user_id)
        
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
            f"✅ <b>Файл успешно загружен!</b>\n\n"
            f"🔗 <b>Ссылка для скачивания:</b>\n"
            f"<code>{link}</code>\n\n"
            f"ℹ️ Нажмите на ссылку выше, чтобы скопировать её",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        
        # Сбрасываем состояние
        await state.clear()
    else:
        # Если не файл, просим отправить файл
        keyboard = create_cancel_keyboard()
        await message.answer("❌ Пожалуйста, отправьте файл (документ, фото, видео и т.д.)", reply_markup=keyboard)
        return

# Обработчик команды /start с параметром
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Сохраняем пользователя в базу данных
    save_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
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
        file_info = get_file_from_db(code, user_id)
        if file_info:
            logging.info(f"Найден файл с кодом {code}, тип: {file_info['file_type']}")
            try:
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
                        document=file_info['telegram_file_id'],
                        caption=file_info.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=file_info['telegram_file_id'],
                        caption=file_info.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'video':
                    await bot.send_video(
                        chat_id=chat_id,
                        video=file_info['telegram_file_id'],
                        caption=file_info.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=file_info['telegram_file_id'],
                        caption=file_info.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=file_info['telegram_file_id'],
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=chat_id,
                        video_note=file_info['telegram_file_id'],
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'animation':
                    await bot.send_animation(
                        chat_id=chat_id,
                        animation=file_info['telegram_file_id'],
                        caption=file_info.get('caption', ''),
                        reply_markup=keyboard
                    )
                elif file_info['file_type'] == 'sticker':
                    # Для стикеров сначала отправляем стикер, потом кнопку отдельно
                    await bot.send_sticker(
                        chat_id=chat_id,
                        sticker=file_info['telegram_file_id']
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
        
        # ИЗМЕНЕННОЕ ПРИВЕТСТВИЕ
        welcome_text = (
            "👋 Привет!\n"
            "📂 Я храню файлы с канала Dima Griefer\n\n"
            "⚠️ Если бот не отвечает или работает некорректно — напишите сюда:\n"
            "👉 @dimagriefer_bot"
        )
        
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
        
        # ИЗМЕНЕННОЕ ПРИВЕТСТВИЕ
        welcome_text = (
            "👋 Привет!\n"
            "📂 Я храню файлы с канала Dima Griefer\n\n"
            "⚠️ Если бот не отвечает или работает некорректно — напишите сюда:\n"
            "👉 @dimagriefer_bot"
        )
        
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

# Основная функция
async def main():
    # Инициализируем базу данных
    init_database()
    
    logging.info("Бот запускается...")
    logging.info(f"Разработчик (владелец): {DEVELOPER_ID}")
    logging.info(f"Текущее количество пользователей в БД: {get_users_count()}")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
