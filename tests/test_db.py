"""
Тесты для модуля db.py.
Покрывают все функции с позитивными и негативными сценариями.
"""


import pytest

from db import (
    add_file,
    add_user,
    get_file_path_by_id,
    get_file_rating,
    get_user_files,
    init_db,
    rate_file,
    search_files,
)


@pytest.fixture
def test_db(tmp_path):
    """Создаёт временную БД для каждого теста."""
    db_path = tmp_path / "test_lecture_lens.db"
    init_db(str(db_path))
    return str(db_path)


# === Тесты для add_user ===


def test_add_user_success(test_db):
    """Успешное добавление пользователя."""
    result = add_user(123, "Алексей", db_path=test_db)
    assert result is True

    # Проверка в БД
    import sqlite3

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM users WHERE user_id = ?", (123,))
    assert cur.fetchone()[0] == "Алексей"
    conn.close()


def test_add_user_invalid_id():
    """Некорректный user_id."""
    with pytest.raises(ValueError, match="положительным целым числом"):
        add_user(-1, "Имя")


def test_add_user_empty_name():
    """Пустое имя."""
    with pytest.raises(ValueError, match="непустой строкой"):
        add_user(123, "")


# === Тесты для add_file ===


def test_add_file_success(test_db):
    """Успешное добавление файла."""
    add_user(101, "Иван", db_path=test_db)
    file_id = add_file(
        101, "storage/test.pdf", "матан, лекция", "лекция.pdf", db_path=test_db
    )
    assert isinstance(file_id, int)
    assert file_id > 0


def test_add_file_nonexistent_user(test_db):
    """Файл от несуществующего пользователя."""
    with pytest.raises(ValueError, match="не найден"):
        add_file(999, "x.txt", "тег", "x.txt", db_path=test_db)


def test_add_file_invalid_input(test_db):
    """Некорректные входные данные."""
    add_user(200, "Вася", db_path=test_db)
    with pytest.raises(ValueError):
        add_file(200, "", "тег", "x.txt", db_path=test_db)
    with pytest.raises(ValueError):
        add_file(200, "x.txt", "", "x.txt", db_path=test_db)
    with pytest.raises(ValueError):
        add_file(200, "x.txt", "тег", "", db_path=test_db)


# === Тесты для search_files ===


def test_search_files_success(test_db):
    """Успешный поиск с автором и рейтингом."""
    add_user(300, "Олег", db_path=test_db)
    file_id = add_file(
        300, "storage/lec.pdf", "матан, пределы", "Лекция.pdf", db_path=test_db
    )
    rate_file(file_id, 300, 4, db_path=test_db)

    results = search_files("матан", db_path=test_db)
    assert len(results) == 1
    item = results[0]
    assert item["original_name"] == "Лекция.pdf"
    assert item["author_name"] == "Олег"
    assert item["rating"] == 4.0


def test_search_files_no_match(test_db):
    """Нет совпадений."""
    add_user(301, "Анна", db_path=test_db)
    add_file(301, "x.pdf", "физика", "Физика.pdf", db_path=test_db)

    results = search_files("матан", db_path=test_db)
    assert results == []


def test_search_files_empty_query():
    """Пустой запрос."""
    with pytest.raises(ValueError, match="не может быть пустым"):
        search_files("")


# === Тесты для get_file_path_by_id ===


def test_get_file_path_by_id_success(test_db):
    """Получение пути по ID."""
    add_user(400, "Катя", db_path=test_db)
    file_id = add_file(
        400, "storage/notes.txt", "конспект", "notes.txt", db_path=test_db
    )

    path = get_file_path_by_id(file_id, db_path=test_db)
    assert path == "storage/notes.txt"


def test_get_file_path_by_id_not_found():
    """Файл не найден."""
    path = get_file_path_by_id(99999, db_path="nonexistent.db")
    assert path is None


# === Тесты для get_user_files ===


def test_get_user_files_success(test_db):
    """Получение файлов пользователя."""
    add_user(500, "Дима", db_path=test_db)
    file_id = add_file(
        500, "storage/diff.pdf", "диффуры", "Диффуры.pdf", db_path=test_db
    )
    rate_file(file_id, 500, 5, db_path=test_db)

    files = get_user_files(500, db_path=test_db)
    assert len(files) == 1
    f = files[0]
    assert f["original_name"] == "Диффуры.pdf"
    assert f["rating"] == 5.0


def test_get_user_files_no_files(test_db):
    """Пользователь без файлов."""
    add_user(501, "Лена", db_path=test_db)
    files = get_user_files(501, db_path=test_db)
    assert files == []


def test_get_user_files_invalid_user():
    """Некорректный user_id."""
    files = get_user_files(-1, db_path="x.db")
    assert files == []


# === Тесты для rate_file и get_file_rating ===


def test_rate_file_success(test_db):
    """Успешная оценка."""
    add_user(600, "Сергей", db_path=test_db)
    file_id = add_file(
        600, "storage/file.pdf", "тест", "test.pdf", db_path=test_db
    )

    result = rate_file(file_id, 600, 3, db_path=test_db)
    assert result is True

    rating = get_file_rating(file_id, db_path=test_db)
    assert rating == 3.0


def test_rate_file_update(test_db):
    """Обновление оценки."""
    add_user(601, "Нина", db_path=test_db)
    add_user(602, "Петр", db_path=test_db)
    file_id = add_file(601, "x.pdf", "x", "x.pdf", db_path=test_db)

    rate_file(file_id, 601, 2, db_path=test_db)
    rate_file(file_id, 602, 4, db_path=test_db)
    rate_file(file_id, 601, 5, db_path=test_db)  # обновление

    rating = get_file_rating(file_id, db_path=test_db)
    # (5 + 4) / 2 = 4.5
    assert abs(rating - 4.5) < 0.01


def test_rate_file_invalid_rating(test_db):
    """Оценка вне диапазона."""
    add_user(603, "Юра", db_path=test_db)
    file_id = add_file(603, "y.pdf", "y", "y.pdf", db_path=test_db)

    with pytest.raises(ValueError, match="от 1 до 5"):
        rate_file(file_id, 603, 6, db_path=test_db)
    with pytest.raises(ValueError, match="от 1 до 5"):
        rate_file(file_id, 603, 0, db_path=test_db)


def test_get_file_rating_no_ratings(test_db):
    """Рейтинг без оценок."""
    add_user(700, "Зоя", db_path=test_db)
    file_id = add_file(700, "z.pdf", "z", "z.pdf", db_path=test_db)

    rating = get_file_rating(file_id, db_path=test_db)
    assert rating == 0.0


def test_get_file_rating_invalid_file_id():
    """Некорректный file_id."""
    with pytest.raises(ValueError, match="положительным целым числом"):
        get_file_rating(-5, db_path="x.db")
