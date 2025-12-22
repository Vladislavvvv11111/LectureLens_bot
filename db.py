"""
Модуль для работы с базой данных SQLite.
Хранит информацию о пользователях, файлах и оценках.
"""

import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def init_db(db_path: str = "lecture_lens.db") -> None:
    """
    Инициализирует базу данных: создаёт таблицы, если их нет.

    Args:
        db_path (str): Путь к файлу базы данных.
        По умолчанию — 'lecture_lens.db'.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            tags TEXT NOT NULL,
            original_name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ratings (
            file_id INTEGER,
            user_id INTEGER,
            rating INTEGER CHECK (rating BETWEEN 1 AND 5),
            PRIMARY KEY (file_id, user_id),
            FOREIGN KEY (file_id) REFERENCES files (file_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )

    conn.commit()
    conn.close()


def add_user(
        user_id: int, name: str, db_path: str = "lecture_lens.db"
) -> bool:
    """
    Добавляет пользователя в базу данных или обновляет его имя,
    если он уже существует.

    Args:
        user_id (int): Уникальный идентификатор пользователя Telegram.
        name (str): Имя или никнейм, указанный пользователем.
        db_path (str): Путь к файлу базы данных.

    Returns:
        bool: True, если операция прошла успешно; False в случае ошибки.

    Raises:
        ValueError: Если входные данные некорректны.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id должен быть положительным целым числом.")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Имя должно быть непустой строкой.")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, name) VALUES (?, ?)",
            (user_id, name.strip()),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("Ошибка при добавлении пользователя: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def add_file(
    user_id: int,
    file_path: str,
    tags: str,
    original_name: str,
    db_path: str = "lecture_lens.db",
) -> Optional[int]:
    """
    Добавляет информацию о файле в базу данных.

    Args:
        user_id (int): ID пользователя, загрузившего файл.
        file_path (str): Относительный путь к файлу
        (например, 'storage/lecture1.pdf').
        tags (str): Ключевые слова, разделённые запятыми
        (например, 'матан, пределы, лекция').
        original_name (str):
        Человекочитаемое имя файла (без технических префиксов).
        db_path (str): Путь к файлу базы данных.

    Returns:
        Optional[int]: ID нового файла (file_id) в случае успеха,
        None — при ошибке.

    Raises:
        ValueError: Если входные данные некорректны.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id должен быть положительным целым числом.")
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path должен быть непустой строкой.")
    if not isinstance(tags, str) or not tags.strip():
        raise ValueError("tags должен быть непустой строкой.")
    if not isinstance(original_name, str) or not original_name.strip():
        raise ValueError("original_name должен быть непустой строкой.")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Проверим, существует ли пользователь
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            raise ValueError(
                f'''Пользователь с user_id={user_id} не найден.
                Вызовите add_user.'''
            )

        cursor.execute(
            "INSERT INTO files (user_id, file_path, tags, original_name)"
            "VALUES (?, ?, ?, ?)",
            (user_id, file_path.strip(), tags.strip(), original_name.strip()),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error("Ошибка при добавлении файла: %s", e)
        return None
    finally:
        if conn:
            conn.close()


def search_files(query: str, db_path: str = "lecture_lens.db") -> list[dict]:
    """
    Ищет файлы, теги которых содержат хотя бы одно слово из запроса.
    Возвращает также имя автора.

    Args:
        query (str): Строка поиска (например, "матан лекция").
        db_path (str): Путь к файлу базы данных.

    Returns:
        list[dict]: Список словарей с ключами:
            - 'file_id': int
            - 'file_path': str
            - 'tags': str
            - 'original_name': str
            - 'author_name': str
            - 'rating': float

    Raises:
        ValueError: Если query пустой.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Запрос для поиска не может быть пустым.")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT f.file_id, f.file_path, f.tags, f.original_name, u.name
                FROM files f
                JOIN users u ON f.user_id = u.user_id
            """
        )
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("Ошибка при поиске файлов: %s", e)
        return []
    finally:
        if conn:
            conn.close()

    query_words = set(word.lower() for word in query.strip().split())
    results = []

    for row in rows:
        file_id, file_path, tags, original_name, author_name = row
        tag_words = set(word.strip().lower() for word in tags.split(","))
        if query_words & tag_words:
            results.append(
                {
                    "file_id": file_id,
                    "file_path": file_path,
                    "original_name": original_name,
                    "tags": tags,
                    "author_name": author_name,
                    "rating": get_file_rating(file_id, db_path),
                }
            )

    return results


def get_file_path_by_id(
    file_id: int, db_path: str = "lecture_lens.db"
) -> Optional[str]:
    """
    Возвращает путь к файлу по его ID.

    Args:
        file_id (int): ID файла.
        db_path (str): Путь к БД.

    Returns:
        Optional[str]: Путь к файлу или None, если не найден.
    """
    if not isinstance(file_id, int) or file_id <= 0:
        return None

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path FROM files WHERE file_id = ?", (file_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        if conn:
            conn.close()


def get_user_files(
        user_id: int, db_path: str = "lecture_lens.db"
) -> list[dict]:
    """
    Возвращает список файлов, загруженных пользователем.

    Args:
        user_id (int): ID пользователя.
        db_path (str): Путь к БД.

    Returns:
        list[dict]:
        Список файлов с полями: file_id, original_name, tags, rating.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        return []

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_id, original_name, tags FROM files WHERE user_id = ?
        """,
            (user_id,),
        )
        rows = cursor.fetchall()
    except sqlite3.Error:
        return []
    finally:
        if conn:
            conn.close()

    results = []
    for row in rows:
        file_id, original_name, tags = row
        rating = get_file_rating(file_id, db_path)
        results.append(
            {
                "file_id": file_id,
                "original_name": original_name,
                "tags": tags,
                "rating": rating,
            }
        )
    return results


def rate_file(
    file_id: int, user_id: int, rating: int, db_path: str = "lecture_lens.db"
) -> bool:
    """
    Оценивает файл пользователем. Если оценка уже есть — обновляет её.

    Args:
        file_id (int): ID файла.
        user_id (int): ID пользователя.
        rating (int): Оценка от 1 до 5.
        db_path (str): Путь к файлу базы данных.

    Returns:
        bool: True — успех, False — ошибка.

    Raises:
        ValueError: Если входные данные некорректны.
    """
    if not isinstance(file_id, int) or file_id <= 0:
        raise ValueError("file_id должен быть положительным целым числом.")
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id должен быть положительным целым числом.")
    if not isinstance(rating, int) or not (1 <= rating <= 5):
        raise ValueError("Оценка должна быть целым числом от 1 до 5.")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()

        # Проверим, существует ли файл
        cursor.execute("SELECT 1 FROM files WHERE file_id = ?", (file_id,))
        if not cursor.fetchone():
            raise ValueError(f"Файл с file_id={file_id} не найден.")

        # Вставка или обновление (UPSERT)
        cursor.execute(
            '''INSERT INTO ratings (file_id, user_id, rating)
            VALUES (?, ?, ?) '''
            '''ON CONFLICT(file_id, user_id)
            DO UPDATE SET rating = excluded.rating''',
            (file_id, user_id, rating),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("Ошибка при оценке файла: %s", e)
        return False
    finally:
        if conn:
            conn.close()


def get_file_rating(file_id: int, db_path: str = "lecture_lens.db") -> float:
    """
    Возвращает средний рейтинг файла. Если оценок нет — возвращает 0.0.

    Args:
        file_id (int): ID файла.
        db_path (str): Путь к файлу базы данных.

    Returns:
        float: Средний рейтинг (от 1.0 до 5.0) или 0.0, если оценок нет.

    Raises:
        ValueError: Если file_id некорректен.
    """
    if not isinstance(file_id, int) or file_id <= 0:
        raise ValueError("file_id должен быть положительным целым числом.")

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT AVG(rating) FROM ratings WHERE file_id = ?", (file_id,)
        )
        avg = cursor.fetchone()[0]
        return float(avg) if avg is not None else 0.0
    except sqlite3.Error as e:
        logger.error("Ошибка при получении рейтинга: %s", e)
        return 0.0
    finally:
        if conn:
            conn.close()
