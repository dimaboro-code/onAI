from unittest.mock import patch

import pytest

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from src.database import (
    Base,
    DBMessage,
    Role,
    insert_message,
    get_all_messages,
    delete_message_by_id,
    delete_all_messages,
    create_tables
)

# Тестовый URL для базы данных в памяти (SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.mark.asyncio
async def test_insert_message_no_fixtures():
    """
    Тест, который создаёт базу в памяти, создаёт таблицы,
    открывает сессию и проверяет insert_message — без использования фикстур.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
        async with SessionLocal() as session:
            inserted = await insert_message(session, "Первое сообщение", Role.user)
            assert inserted is not None
            assert inserted.id is not None
            assert inserted.content == "Первое сообщение"
            assert inserted.role == Role.user

            result = await session.execute(select(DBMessage).where(DBMessage.id == inserted.id))
            from_db = result.scalar_one_or_none()
            assert from_db is not None
            assert from_db.id == inserted.id
            assert from_db.content == inserted.content
            assert from_db.role == inserted.role

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_get_all_messages_no_fixtures():
    """
    Тестирует получение всех сообщений без использования Pytest‐фикстур.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(bind=engine, autocommit=False, autoflush=False)

        async with SessionLocal() as session:
            await delete_all_messages(session)
            await insert_message(session, "Сообщение #1", Role.user)
            await insert_message(session, "Сообщение #2", Role.assistant)
            await insert_message(session, "Сообщение #3", Role.user)
            messages = await get_all_messages(session)
            assert len(messages) == 3
            contents = [msg.content for msg in messages]
            assert contents == ["Сообщение #1", "Сообщение #2", "Сообщение #3"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_message_by_id_no_fixtures():
    """
    Тестирует удаление сообщения по ID без Pytest-фикстур.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(bind=engine, autocommit=False, autoflush=False)
        async with SessionLocal() as session:
            await delete_all_messages(session)
            msg = await insert_message(session, "Удаляемое сообщение", Role.assistant)
            msg_id = msg.id
            await delete_message_by_id(session, msg_id)
            messages_after_delete = await get_all_messages(session)
            assert len(messages_after_delete) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_all_messages_no_fixtures():
    """
    Тест полного удаления всех сообщений, без использования Pytest-фикстур.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        SessionLocal = async_sessionmaker(bind=engine, autocommit=False, autoflush=False)
        async with SessionLocal() as session:
            await insert_message(session, "Temp #1", Role.user)
            await insert_message(session, "Temp #2", Role.assistant)
            await delete_all_messages(session)
            messages = await get_all_messages(session)
            assert len(messages) == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_tables():
    """
    Тест для функции create_tables. В реальном проекте можно запускать
    только один раз, но здесь для полноты примера проверяем, что таблицы создаются.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    with patch("src.database.engine", engine):
        await create_tables()

    table_names = Base.metadata.tables.keys()
    assert "messages" in table_names
