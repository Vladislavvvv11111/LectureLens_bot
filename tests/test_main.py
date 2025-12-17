"""
Тесты для main.py — с полным мокированием объектов Telegram.
"""

import os
from unittest.mock import AsyncMock

import pytest

from db import add_file, add_user, init_db
from main import (
    DB_PATH,
    STORAGE_DIR,
    clean_filename,
    receive_file_id_for_download,
    receive_name,
    receive_rating_input,
    receive_search_query,
    receive_tags,
    show_profile,
)


@pytest.fixture
def test_db():
    init_db(DB_PATH)
    yield DB_PATH
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    if os.path.exists(STORAGE_DIR):
        for f in os.listdir(STORAGE_DIR):
            os.remove(os.path.join(STORAGE_DIR, f))
        os.rmdir(STORAGE_DIR)


@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.user_data = {}
    return context


@pytest.fixture
def make_mock_update():
    """Мок Update без реальных объектов Telegram."""

    def _make_mock_update(user_id=12345, text=""):
        message = AsyncMock()
        message.text = text
        message.reply_text = AsyncMock()
        message.reply_document = AsyncMock()

        update = AsyncMock()
        update.message = message
        update.effective_user.id = user_id
        return update

    return _make_mock_update


# === Тесты ===


def test_clean_filename():
    assert clean_filename("лекция?.pdf") == "лекция.pdf"


@pytest.mark.asyncio
async def test_receive_name_success(make_mock_update, mock_context, test_db):
    mock_update = make_mock_update(text="Алексей")
    await receive_name(mock_update, mock_context)
    assert "Алексей" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_receive_tags_success(make_mock_update, mock_context, test_db):
    # Добавляем пользователя в БД
    add_user(12345, "Тест_Пользователь", db_path=test_db)

    mock_update = make_mock_update()
    mock_context.user_data.update(
        {
            "uploading_file_path": "storage/test.pdf",
            "uploading_original_name": "лекция.pdf",
            "uploader_user_id": 12345,
        }
    )
    mock_update.message.text = "матан, лекция"
    await receive_tags(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "✅ Файл успешно загружен!" in text
    assert "лекция.pdf" in text


@pytest.mark.asyncio
async def test_receive_search_query_success(
        make_mock_update, mock_context, test_db
):
    add_user(101, "Автор", DB_PATH)
    add_file(101, "x", "матан", "lec.pdf", DB_PATH)
    mock_update = make_mock_update(text="матан")
    await receive_search_query(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Автор" in text


@pytest.mark.asyncio
async def test_receive_rating_input_success(
        make_mock_update, mock_context, test_db
):
    add_user(200, "X", DB_PATH)
    fid = add_file(200, "x", "x", "x.pdf", DB_PATH)
    mock_update = make_mock_update(user_id=200, text=f"{fid} 5")
    await receive_rating_input(mock_update, mock_context)
    assert "оценён на 5" in mock_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_receive_file_id_for_download_success(
    make_mock_update, mock_context, test_db
):
    add_user(300, "X", DB_PATH)
    fid = add_file(300, "storage/test.txt", "x", "test.txt", DB_PATH)
    os.makedirs(STORAGE_DIR, exist_ok=True)
    with open(os.path.join(STORAGE_DIR, "test.txt"), "w") as f:
        f.write("ok")
    mock_update = make_mock_update(text=str(fid))
    await receive_file_id_for_download(mock_update, mock_context)
    assert mock_update.message.reply_document.called


@pytest.mark.asyncio
async def test_show_profile_success(make_mock_update, mock_context, test_db):
    add_user(400, "Профиль", DB_PATH)
    add_file(400, "x", "x", "p.pdf", DB_PATH)
    mock_update = make_mock_update(user_id=400)
    await show_profile(mock_update, mock_context)
    text = mock_update.message.reply_text.call_args[0][0]
    assert "Профиль" in text
