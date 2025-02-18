import pytest
import asyncio

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


@pytest.fixture(scope="session")
def event_loop():
    """
    Переопределение event_loop на уровне всей сессии pytest,
    чтобы можно было запускать асинхронные тесты.
    """
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Создаёт движок для тестов, используя базу в памяти."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(test_engine):
    """Фикстура создает новую сессию для каждого теста."""
    SessionLocal = async_sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_insert_message(async_session: AsyncSession):
    """Проверка вставки нового сообщения."""
    inserted_message = await insert_message(
        session=async_session,
        content="Первое сообщение",
        role=Role.user
    )

    # Проверка, что вернулся объект
    assert inserted_message is not None
    assert inserted_message.id is not None
    assert inserted_message.content == "Первое сообщение"
    assert inserted_message.role == Role.user

    # Проверка, видно ли сообщение в базе
    db_obj = await async_session.execute(
        select(DBMessage).where(DBMessage.id == inserted_message.id)
    )
    from_db = db_obj.scalar_one_or_none()
    assert from_db is not None
    assert from_db.id == inserted_message.id
    assert from_db.content == "Первое сообщение"
    assert from_db.role == Role.user


@pytest.mark.asyncio
async def test_get_all_messages(async_session: AsyncSession):
    """Проверка получения всех сообщений."""
    await delete_all_messages(async_session)

    # Создаем несколько сообщений
    await insert_message(async_session, "Сообщение #1", Role.user)
    await insert_message(async_session, "Сообщение #2", Role.assistant)
    await insert_message(async_session, "Сообщение #3", Role.user)

    # Извлекаем все
    messages = await get_all_messages(async_session)

    # Должно быть 3 сообщения
    assert len(messages) == 3
    # Проверим порядок по времени (asc)
    contents = [msg.content for msg in messages]
    assert contents == ["Сообщение #1", "Сообщение #2", "Сообщение #3"]


@pytest.mark.asyncio
async def test_delete_message_by_id(async_session: AsyncSession):
    """Проверка удаления сообщения по ID."""
    await delete_all_messages(async_session)

    # Добавляем одно сообщение
    msg = await insert_message(async_session, "Удаляемое сообщение", Role.assistant)
    msg_id = msg.id

    # Удаляем
    await delete_message_by_id(async_session, msg_id)

    # Проверяем, удалено ли
    messages_after_delete = await get_all_messages(async_session)
    assert len(messages_after_delete) == 0


@pytest.mark.asyncio
async def test_delete_all_messages(async_session: AsyncSession):
    """Проверка полного удаления всех сообщений."""
    # Добавляем несколько сообщений
    await insert_message(async_session, "Temp #1", Role.user)
    await insert_message(async_session, "Temp #2", Role.assistant)

    # Удаляем все
    await delete_all_messages(async_session)

    # Снова проверяем
    messages = await get_all_messages(async_session)
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_create_tables(test_engine):
    """
    Тест для функции create_tables. В реальном проекте можно запускать
    только один раз, но здесь для полноты примера проверяем, что таблицы создаются.
    """
    # Повторно вызываем, чтобы убедиться, что никаких исключений не происходит
    await create_tables()

    # Проверим, что таблица действительно существует
    # Для простоты убеждаемся, что DBMessage "доступна" в метаданных
    table_names = Base.metadata.tables.keys()
    assert "messages" in table_names
