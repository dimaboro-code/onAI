import aio_pika
from fastapi import HTTPException
from starlette.responses import Response

from src.config import RABBITMQ_URL, QUEUE_NAME, logger
from src.models import InputMessage


class RabbitMQService:
    """
    Класс-обёртка для работы с RabbitMQ, обеспечивающий ленивое подключение.
    """

    def __init__(self, url: str, queue_name: str):
        self.url = url
        self.queue_name = queue_name
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None

    async def connect(self) -> aio_pika.Channel:
        """
        Создаёт и/или возвращает активный канал RabbitMQ.
        При необходимости (если соединение или канал закрыты) —
        переподключается, заново открывает канал и декларирует очередь.
        """
        if not self._connection or self._connection.is_closed:
            logger.info("🔄 Подключение к RabbitMQ...")
            self._connection = await aio_pika.connect_robust(self.url)
            logger.info("✅ Соединение с RabbitMQ установлено.")

        if not self._channel or self._channel.is_closed:
            logger.info("🔄 Создание канала RabbitMQ...")
            self._channel = await self._connection.channel()
            await self._channel.declare_queue(self.queue_name, durable=True)
            logger.info(f"✅ Очередь '{self.queue_name}' создана/существует.")

        return self._channel

    async def send_message(self, message: InputMessage) -> Response:
        """
        Публикует сообщение в очередь RabbitMQ, предварительно убеждаясь,
        что соединение и канал готовы к работе.
        """
        try:
            channel = await self.connect()
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message.model_dump_json().encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=self.queue_name,
            )
            logger.info("📩 Сообщение отправлено в RabbitMQ.")
            return Response(status_code=200, content="✅ Сообщение отправлено")
        except Exception as e:
            logger.exception("❌ Ошибка публикации сообщения в RabbitMQ:", exc_info=e)
            raise HTTPException(status_code=500, detail="Ошибка RabbitMQ")

    async def close_connection(self) -> None:
        """
        Закрывает соединение с RabbitMQ, если оно активно.
        """
        if self._connection and not self._connection.is_closed:
            logger.info("🔄 Закрытие соединения с RabbitMQ...")
            await self._connection.close()
            logger.info("✅ Соединение с RabbitMQ закрыто.")


rabbitmq_service = RabbitMQService(RABBITMQ_URL, QUEUE_NAME)
