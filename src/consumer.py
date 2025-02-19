import asyncio

import aio_pika
import httpx
from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import logger, RABBITMQ_URL, QUEUE_NAME
from src.database import (
    get_async_session,
    insert_message,
    Role,
    get_all_messages,
    DBMessage,
    create_tables,
)
from src.models import InputMessage
from src.openai_service import get_answer


def get_messages_list_as_json(messages: list[DBMessage]) -> list[dict]:
    """
    Преобразует список объектов DBMessage в список словарей
    для удобной передачи в OpenAI.
    """
    return [
        {
            "role": message.role,
            "content": message.content
        }
        for message in messages
    ]


async def process_message(session: AsyncSession, input_message: InputMessage) -> str:
    """
    Сохраняет входящее сообщение в БД, получает всю историю сообщений
    и запрашивает ответ у AI-модели. Затем сохраняет ответ в БД и возвращает его.
    """
    await insert_message(session, input_message.message, Role.user)

    all_msgs = await get_all_messages(session)
    all_msgs_json = get_messages_list_as_json(all_msgs)
    logger.debug(f"🔹 Текущая история диалога: {all_msgs_json}")

    answer = await get_answer(all_msgs_json)
    logger.info("✅ Ответ от AI получен")
    logger.debug(f"📜 Ответ: {answer}")

    await insert_message(session, answer, Role.assistant)

    return answer


async def send_answer(callback_url: HttpUrl, answer: str) -> None:
    """
    Отправляет ответ (answer) по указанному callback_url,
    логируя результат и обрабатывая возможные ошибки.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(str(callback_url), json={"message": answer})
            logger.info(f"📨 Ответ отправлен, статус-код: {response.status_code}")
    except httpx.HTTPError as exc:
        logger.error(f"❌ Ошибка при отправке ответа: {exc}")


async def callback(message: aio_pika.IncomingMessage) -> None:
    """
    Колбэк, вызываемый при получении сообщения из очереди.
    Обрабатывает входящее сообщение (InputMessage), формирует ответ от AI
    и отправляет его на callback_url.
    """
    logger.info("📩 Получено новое сообщение от RabbitMQ")

    input_message = InputMessage.model_validate_json(message.body.decode())

    async with message.process():
        async with get_async_session() as session:
            answer = await process_message(session, input_message)
            await send_answer(input_message.callback_url, answer)


async def consume() -> None:
    """
    Слушает сообщения в очереди RabbitMQ в бесконечном цикле
    (пока не будет прервано приложение).
    """
    await create_tables()

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)

        logger.info("🔄 Ожидание сообщений от RabbitMQ...")
        await queue.consume(callback)

        await asyncio.Future()


async def main() -> None:
    """
    Точка входа в приложение: запускает прослушивание очереди,
    обрабатывает возможные исключения, связанные с RabbitMQ и БД.
    """
    try:
        await consume()
    except (aio_pika.exceptions.AMQPError, ConnectionError) as exc:
        logger.exception("❌ Ошибка соединения с RabbitMQ:", exc_info=exc)
    except Exception as exc:
        logger.exception("❌ Непредвиденная ошибка:", exc_info=exc)


if __name__ == "__main__":
    asyncio.run(main())