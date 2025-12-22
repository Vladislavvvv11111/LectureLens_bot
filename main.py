"""
Telegram-бот LectureLens Bot: обмен учебными материалами.
Все действия — через кнопки.
"""

import logging
import os
import re
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from db import (
    add_file,
    add_user,
    get_file_path_by_id,
    get_user_files,
    init_db,
    rate_file,
    search_files,
)

load_dotenv()

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
AWAITING_NAME = 0
AWAITING_FILE = 1
AWAITING_TAGS = 2
AWAITING_SEARCH_QUERY = 3
AWAITING_RATING_INPUT = 4
AWAITING_FILE_ID_FOR_DOWNLOAD = 5

# Путь к БД и хранилищу через переменные окружения
DB_PATH = os.getenv("DB_PATH", "lecture_lens.db")
STORAGE_DIR = os.getenv("STORAGE_DIR", "storage")

# Главное меню
MAIN_MENU = [
    ["📌 Указать имя", "👤 Мой профиль"],
    ["📤 Загрузить файл", "📥 Скачать файл"],
    ["🔍 Найти файл", "⭐ Оценить файл"],
]

MAIN_MENU_BUTTONS = {
    "📌 Указать имя",
    "👤 Мой профиль",
    "📤 Загрузить файл",
    "📥 Скачать файл",
    "🔍 Найти файл",
    "⭐ Оценить файл",
}
MAIN_MARKUP = ReplyKeyboardMarkup(
    MAIN_MENU, resize_keyboard=True, one_time_keyboard=False
)


def clean_filename(filename: str) -> str:
    """
    Очищает имя файла от недопустимых символов.
    Оставляет только буквы, цифры, пробелы, точки, подчёркивания и дефисы.
    Также ограничивает длину имени до 100 символов.

    Args:
        filename (str): Исходное имя файла, возможно содержащее недопустимые символы.

    Returns:
        str: Очищенное и безопасное имя файла. Если результат пустой,
             возвращается 'unnamed_file'.
    """
    cleaned = re.sub(r"[^\w\s\.\-]", "", filename)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > 100:
        name, ext = os.path.splitext(cleaned)
        cleaned = name[:90] + ext
    return cleaned or "unnamed_file"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправляет приветственное сообщение и отображает главное меню пользователю.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             означающее завершение любого активного диалога.
    """
    user = update.effective_user
    logging.info("Пользователь %s начал диалог", user.full_name)
    await update.message.reply_text(
        "Привет! 👋 Я — LectureLens Bot.\n"
        "Помогаю делиться лекциями и конспектами.\n"
        "Выберите действие:",
        reply_markup=MAIN_MARKUP,
    )
    return ConversationHandler.END


async def ask_for_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Запрашивает у пользователя его имя после нажатия кнопки 'Указать имя'.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_NAME, ожидая ввода имени.
    """
    await update.message.reply_text(
        "Пожалуйста, введите ваше имя или никнейм:"
    )
    return AWAITING_NAME


async def receive_name(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Обрабатывает введённое пользователем имя: проверяет его корректность
    и сохраняет в базу данных.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             возвращая пользователя в главное меню.
    """
    text = update.message.text.strip()
    if text in MAIN_MENU_BUTTONS:
        await update.message.reply_text("Сначала завершите ввод имени.")
        return AWAITING_NAME
    if not text:
        await update.message.reply_text(
            "Имя не может быть пустым. Попробуйте снова:"
        )
        return AWAITING_NAME

    user_id = update.effective_user.id
    success = add_user(user_id, text, db_path=DB_PATH)
    if success:
        await update.message.reply_text(
            f"Отлично! Вас зовут: {text}", reply_markup=MAIN_MARKUP
        )
    else:
        await update.message.reply_text(
            "❌ Ошибка сохранения. Попробуйте позже.",
            reply_markup=MAIN_MARKUP,
        )
    return ConversationHandler.END


async def ask_for_file(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Запрашивает у пользователя отправку файла для загрузки.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_FILE, ожидая отправки документа.
    """
    await update.message.reply_text(
        "Отправьте файл (PDF, DOC, TXT и т.д.):"
    )
    return AWAITING_FILE


async def receive_file(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Принимает загруженный пользователем файл, проверяет его формат,
    сохраняет на диск и запрашивает теги для индексации.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_TAGS, если файл принят;
             иначе остаётся в AWAITING_FILE для повторной попытки.
    """
    if not update.message.document:
        await update.message.reply_text(
            "Пожалуйста, отправьте именно файл (не фото/текст)."
        )
        return AWAITING_FILE

    document = update.message.document
    original_name = document.file_name or "document"

    allowed_ext = {".pdf", ".doc", ".docx", ".txt", ".ppt", ".pptx"}
    _, ext = os.path.splitext(original_name)
    if ext.lower() not in allowed_ext:
        await update.message.reply_text(
            "Поддерживаются только учебные форматы: PDF, DOC(X), TXT, PPT(X)."
        )
        return AWAITING_FILE

    clean_name = clean_filename(original_name)
    timestamp = int(datetime.now().timestamp())
    safe_filename = f"{update.effective_user.id}_{clean_name}_{timestamp}{ext}"
    file_path = os.path.join(STORAGE_DIR, safe_filename)

    try:
        file = await document.get_file()
        await file.download_to_drive(file_path)
    except (PermissionError, OSError) as e:
        # Ошибки файловой системы
        logger.error(f"Ошибка при сохранении файла {file_path}: {e}")
        await update.message.reply_text(
            "Не удалось сохранить файл: возможно, нет праав на запись или закончилось место на диске. "
            "Попробуйте позже."
        )
        return AWAITING_FILE
    except Exception as e:
        # Любые другие непредвиденные ошибки (например, сетевые при get_file)
        logger.exception(f"Неожиданная ошибка при обработке файла: {e}")
        await update.message.reply_text(
            "Произошла непредвиденная ошибка. Пожалуйста, попробуйте отправить файл ещё раз."
        )
        return AWAITING_FILE

    # Сохраняем всё необходимое в контексте
    context.user_data["uploading_file_path"] = file_path
    context.user_data["uploading_original_name"] = clean_name
    context.user_data["uploader_user_id"] = update.effective_user.id

    await update.message.reply_text(
        "Отлично! Теперь введите ключевые слова через запятую "
        "(например: матан, лекция, пределы):"
    )
    return AWAITING_TAGS


async def receive_tags(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Принимает теги от пользователя и сохраняет информацию о файле в базу данных.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             возвращая пользователя в главное меню.
    """
    tags = update.message.text.strip()
    if tags in MAIN_MENU_BUTTONS:
        await update.message.reply_text(
            "Пожалуйста, введите теги, а не нажимайте кнопки."
        )
        return AWAITING_TAGS
    if not tags:
        await update.message.reply_text(
            "Теги не могут быть пустыми. Попробуйте снова:"
        )
        return AWAITING_TAGS

    file_path = context.user_data.get("uploading_file_path")
    original_name = context.user_data.get("uploading_original_name")
    user_id = context.user_data.get("uploader_user_id")

    if not file_path or not original_name or not user_id:
        await update.message.reply_text(
            "❌ Ошибка: данные файла утеряны. Начните заново.",
            reply_markup=MAIN_MARKUP,
        )
        return ConversationHandler.END

    # Передаём original_name!
    file_id = add_file(
        user_id, file_path, tags, original_name, db_path=DB_PATH
    )

    if file_id:
        await update.message.reply_text(
            f"✅ Файл успешно загружен!\n"
            f"ID файла: {file_id}\n"
            f"Название: {original_name}\n"
            f"Теги: {tags}",
            reply_markup=MAIN_MARKUP,
        )
    else:
        await update.message.reply_text(
            "❌ Не удалось сохранить файл. Попробуйте позже.",
            reply_markup=MAIN_MARKUP,
        )

    # Очищаем контекст
    context.user_data.pop("uploading_file_path", None)
    context.user_data.pop("uploading_original_name", None)
    context.user_data.pop("uploader_user_id", None)

    return ConversationHandler.END


async def ask_for_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Запрашивает у пользователя поисковый запрос для поиска файлов по тегам.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_SEARCH_QUERY, ожидая ввода запроса.
    """
    await update.message.reply_text(
        "Введите ключевые слова для поиска "
        "(например: матан лекция или матан, лекция):"
    )
    return AWAITING_SEARCH_QUERY


async def receive_search_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Выполняет поиск файлов по заданным ключевым словам и отправляет результаты.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             возвращая пользователя в главное меню.
    """
    query = update.message.text.strip()
    if query in MAIN_MENU_BUTTONS:
        await update.message.reply_text(
            "Пожалуйста, введите поисковый запрос, а не нажимайте кнопки."
        )
        return AWAITING_SEARCH_QUERY
    if not query:
        await update.message.reply_text(
            "Запрос не может быть пустым. Попробуйте снова:"
        )
        return AWAITING_SEARCH_QUERY

    results = search_files(query, db_path=DB_PATH)

    if not results:
        await update.message.reply_text(
            "❌ Ничего не найдено по вашему запросу.", reply_markup=MAIN_MARKUP
        )
    else:
        response = "📄 Найденные файлы:\n\n"
        for item in results:
            response += (
                f"ID: {item['file_id']} | Название: {item['original_name']}\n"
                f"Автор: {item['author_name']}\n"
                f"Теги: {item['tags']}\n"
                f"Рейтинг: {item['rating']:.1f} ⭐\n"
                f"{'─' * 30}\n"
            )
        await update.message.reply_text(response, reply_markup=MAIN_MARKUP)

    return ConversationHandler.END


async def ask_for_rating(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Запрашивает у пользователя ID файла и оценку (от 1 до 5).

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_RATING_INPUT, ожидая ввода данных об оценке.
    """
    await update.message.reply_text(
        "Введите ID файла и вашу оценку от 1 до 5 через пробел.\n"
        "Пример: 3 5"
    )
    return AWAITING_RATING_INPUT


async def receive_rating_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Обрабатывает ввод пользователя для оценки файла: разбирает ID и оценку,
    проверяет корректность и сохраняет в базу данных.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             возвращая пользователя в главное меню.
    """
    text = update.message.text.strip()

    if text in MAIN_MENU_BUTTONS:
        await update.message.reply_text(
            "Пожалуйста, введите оценку, а не нажимайте кнопки."
        )
        return AWAITING_RATING_INPUT

    try:
        parts = text.split()
        if len(parts) != 2:
            raise ValueError("Неверный формат")

        file_id = int(parts[0])
        rating = int(parts[1])

        if not (1 <= rating <= 5):
            raise ValueError("Оценка вне диапазона")

        user_id = update.effective_user.id
        success = rate_file(file_id, user_id, rating, db_path=DB_PATH)

        if success:
            await update.message.reply_text(
                f"✅ Файл ID={file_id} оценён на {rating}! Спасибо за отзыв!",
                reply_markup=MAIN_MARKUP,
            )
        else:
            await update.message.reply_text(
                "❌ Не удалось сохранить оценку. Проверьте ID файла.",
                reply_markup=MAIN_MARKUP,
            )

    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Неверный формат. Введите: ID_файла оценка (например: 2 4)",
            reply_markup=MAIN_MARKUP,
        )

    return ConversationHandler.END


async def ask_for_download(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Запрашивает у пользователя ID файла, который он хочет скачать.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние AWAITING_FILE_ID_FOR_DOWNLOAD, ожидая ввода ID.
    """
    await update.message.reply_text(
        "Введите ID файла, который хотите скачать "
        "(указан в результатах поиска):"
    )
    return AWAITING_FILE_ID_FOR_DOWNLOAD


async def receive_file_id_for_download(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Обрабатывает введённый ID файла, находит его на диске и отправляет пользователю.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        int: Состояние ConversationHandler.END,
             возвращая пользователя в главное меню.
    """
    text = update.message.text.strip()

    if text in MAIN_MENU_BUTTONS:
        await update.message.reply_text("Пожалуйста, введите ID файла.")
        return AWAITING_FILE_ID_FOR_DOWNLOAD

    try:
        file_id = int(text)
        if file_id <= 0:
            raise ValueError

        # Получаем путь из БД
        file_path = get_file_path_by_id(file_id, db_path=DB_PATH)

        if not file_path or not os.path.isfile(file_path):
            await update.message.reply_text(
                "❌ Файл не найден. Проверьте ID и попробуйте снова.",
                reply_markup=MAIN_MARKUP,
            )
            return ConversationHandler.END

        # Отправляем файл
        await update.message.reply_document(document=open(file_path, "rb"))
        await update.message.reply_text(
            "✅ Файл отправлен!", reply_markup=MAIN_MARKUP
        )

    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Неверный ID. Введите целое положительное число.",
            reply_markup=MAIN_MARKUP,
        )

    return ConversationHandler.END


async def show_profile(
        update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Отображает профиль пользователя: его имя и список загруженных им файлов.

    Args:
        update (Update): Объект, содержащий информацию о входящем сообщении.
        context (ContextTypes.DEFAULT_TYPE): Контекст выполнения обработчика.

    Returns:
        None
    """
    user_id = update.effective_user.id

    # Получаем имя
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
    except sqlite3.Error:
        user_row = None
    finally:
        if conn:
            conn.close()

    if not user_row:
        await update.message.reply_text(
            "Сначала укажите своё имя с помощью кнопки «📌 Указать имя».",
            reply_markup=MAIN_MARKUP,
        )
        return

    name = user_row[0]
    files = get_user_files(user_id, db_path=DB_PATH)

    response = f"👤 Ваш профиль\nИмя: {name}\n\n"
    if not files:
        response += "📂 Вы пока ничего не загрузили."
    else:
        response += f"📂 Ваши файлы ({len(files)}):\n\n"
        for f in files:
            response += (
                f"ID: {f['file_id']} | Название: {f['original_name']}\n"
                f"Теги: {f['tags']}\n"
                f"Рейтинг: {f['rating']:.1f} ⭐\n"
                f"{'─' * 30}\n"
            )

    await update.message.reply_text(
        response, parse_mode=None
    )


def main() -> None:
    """
    Основная функция запуска бота.
    Инициализирует базу данных, создаёт директорию для файлов,
    настраивает обработчики и запускает polling.

    Raises:
        ValueError: Если переменная окружения TELEGRAM_BOT_TOKEN не задана.
    """
    os.makedirs(STORAGE_DIR, exist_ok=True)
    init_db(DB_PATH)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError(
            "Переменная окружения TELEGRAM_BOT_TOKEN не задана!"
        )

    application = Application.builder().token(token).build()

    # Диалоги
    set_name_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📌 Указать имя$"), ask_for_name)
        ],
        states={
            AWAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    upload_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📤 Загрузить файл$"), ask_for_file)
        ],
        states={
            AWAITING_FILE: [
                MessageHandler(filters.Document.ALL, receive_file)
            ],
            AWAITING_TAGS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tags)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    search_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔍 Найти файл$"), ask_for_search)
        ],
        states={
            AWAITING_SEARCH_QUERY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_search_query
                )
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    rate_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⭐ Оценить файл$"), ask_for_rating)
        ],
        states={
            AWAITING_RATING_INPUT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_rating_input
                )
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    download_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📥 Скачать файл$"), ask_for_download)
        ],
        states={
            AWAITING_FILE_ID_FOR_DOWNLOAD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    receive_file_id_for_download,
                )
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(set_name_conv)
    application.add_handler(upload_conv)
    application.add_handler(search_conv)
    application.add_handler(rate_conv)
    application.add_handler(download_conv)
    # Обработчик профиля
    application.add_handler(
        MessageHandler(filters.Regex("^👤 Мой профиль$"), show_profile)
    )

    application.run_polling()


if __name__ == "__main__":
    main()