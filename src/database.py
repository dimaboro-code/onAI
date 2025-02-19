from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from sqlalchemy import Enum as EnumSQL, select, delete
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import logger, DATABASE_URL


engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Role(str, Enum):
    """Роли в базе данных"""
    user = "user"
    assistant = "assistant"


class DBMessage(Base):
    """Таблица сообщений"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)  # UTC - более корректный вариант

    content: Mapped[str]
    role: Mapped[Role] = mapped_column(EnumSQL(Role), nullable=False)


@asynccontextmanager
async def get_async_session() -> AsyncSession:
    """Генератор асинхронных сессий для работы с БД"""
    async with async_session() as session:
        yield session


async def insert_message(session: AsyncSession, content: str, role: Role):
    """Вставляет новое сообщение в базу данных"""
    try:
        new_message = DBMessage(content=content, role=role)
        session.add(new_message)
        await session.commit()
        await session.refresh(new_message)
        logger.info(f"✅ Добавлено сообщение ID={new_message.id} ({role})")
        return new_message
    except Exception as e:
        logger.exception("❌ Ошибка при вставке сообщения:", exc_info=e)
        await session.rollback()
        return None


async def get_all_messages(session: AsyncSession):
    """Извлекает все сообщения из базы"""
    try:
        query = select(DBMessage).order_by(DBMessage.created_at.asc())
        result = await session.execute(query)
        messages = result.scalars().all()
        logger.debug(f"🔹 Загружено {len(messages)} сообщений из БД")
        return messages
    except Exception as e:
        logger.exception("❌ Ошибка при получении всех сообщений:", exc_info=e)
        return []


async def delete_message_by_id(session: AsyncSession, message_id: int):
    """Удаляет сообщение из базы по его ID, в текущей версии не используется"""
    try:
        query = delete(DBMessage).where(DBMessage.id == message_id)
        result = await session.execute(query)
        await session.commit()
        if result.rowcount:
            logger.info(f"🗑 Удалено сообщение ID={message_id}")
        else:
            logger.warning(f"⚠ Сообщение ID={message_id} не найдено")
    except Exception as e:
        logger.exception(f"❌ Ошибка при удалении сообщения ID={message_id}:", exc_info=e)
        await session.rollback()


async def delete_all_messages(session: AsyncSession):
    """Полностью очищает таблицу"""
    try:
        query = delete(DBMessage)
        await session.execute(query)
        await session.commit()
        logger.info("🗑 Все сообщения удалены из БД")
    except Exception as e:
        logger.exception("❌ Ошибка при очистке всех сообщений из БД:", exc_info=e)


async def create_tables():
    """Создание таблиц в БД, если их нет"""
    async with engine.begin() as conn:
        logger.info("🛠 Создание таблиц в БД...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Таблицы успешно созданы.")
