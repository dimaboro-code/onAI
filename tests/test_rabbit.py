import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from starlette.responses import Response

import aio_pika

from src.rabbit import RabbitMQService
from src.models import InputMessage


@pytest.mark.asyncio
async def test_connect_creates_new_connection_and_channel():
    with patch("aio_pika.connect_robust") as mock_connect_robust:
        mock_connection = AsyncMock(spec=aio_pika.RobustConnection)
        mock_connection.is_closed = True
        mock_channel = AsyncMock(spec=aio_pika.Channel)
        mock_channel.declare_queue = AsyncMock()

        mock_connect_robust.return_value = mock_connection
        mock_connection.channel = AsyncMock(return_value=mock_channel)

        service = RabbitMQService("amqp://fake-url", "fake-queue")
        channel = await service.connect()

        mock_connect_robust.assert_called_once_with("amqp://fake-url")
        mock_connection.channel.assert_awaited_once()
        mock_channel.declare_queue.assert_awaited_once_with("fake-queue", durable=True)
        assert channel == mock_channel


@pytest.mark.asyncio
async def test_connect_reuses_open_connection_and_channel():
    """
    Проверяем, что если соединение и канал уже открыты, новый канал не создаётся.
    """
    mock_connection = MagicMock(spec=aio_pika.RobustConnection)
    mock_connection.is_closed = False
    mock_channel = MagicMock(spec=aio_pika.Channel)
    mock_channel.is_closed = False

    with patch("aio_pika.connect_robust") as mock_connect_robust:
        service = RabbitMQService("amqp://fake-url", "fake-queue")
        service._connection = mock_connection
        service._channel = mock_channel

        mock_connect_robust.return_value = mock_connection
        channel = await service.connect()
        mock_connect_robust.assert_not_called()
        mock_connection.channel.assert_not_called()
        assert channel == mock_channel
        channel = await service.connect()
    mock_connect_robust.assert_not_called()
    mock_connection.channel.assert_not_called()
    assert channel == mock_channel


@pytest.mark.asyncio
async def test_send_message_success():
    """
    Проверяем отправку сообщения в случае успеха.
    """
    service = RabbitMQService("amqp://fake-url", "fake-queue")
    mock_channel = AsyncMock(spec=aio_pika.Channel)
    mock_channel.default_exchange = AsyncMock

    service.connect = AsyncMock(return_value=mock_channel)
    mock_publish = AsyncMock()
    mock_channel.default_exchange.publish = mock_publish

    test_message = InputMessage(message="Hello RabbitMQ!", callback_url="http://fake-callback")
    response = await service.send_message(test_message)

    service.connect.assert_awaited_once()
    mock_publish.assert_awaited_once()
    assert isinstance(response, Response)
    assert response.status_code == 200
    assert "Сообщение отправлено" in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_send_message_failure():
    """
    Проверяем, что при ошибке в процессе публикации вызывается HTTPException (500).
    """
    service = RabbitMQService("amqp://fake-url", "fake-queue")
    mock_channel = AsyncMock(spec=aio_pika.Channel)
    mock_channel.default_exchange = AsyncMock
    mock_channel.default_exchange.publish = AsyncMock()
    mock_channel.default_exchange.publish.side_effect = RuntimeError("publish error")

    service.connect = AsyncMock(return_value=mock_channel)
    test_message = InputMessage(message="Broken RabbitMQ!", callback_url="http://fake-callback")
    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(test_message)
    assert exc_info.value.status_code == 500
    assert "Ошибка RabbitMQ" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_close_connection():
    """
    Проверяем, что закрытие соединения действительно вызывает close()
    при открытом соединении, и не вызывает лишнего при уже закрытом.
    """
    def _close_side_effect(*args, **kwargs):
        mock_connection.is_closed = True

    service = RabbitMQService("amqp://fake-url", "fake-queue")
    mock_connection = AsyncMock(spec=aio_pika.RobustConnection)
    mock_connection.is_closed = False

    mock_connection.close = AsyncMock()

    mock_connection.close.side_effect = _close_side_effect
    service._connection = mock_connection

    await service.close_connection()
    mock_connection.close.assert_awaited_once()

    # Попытка повторно закрыть
    await service.close_connection()
    # Повторно close() уже не вызовется (так как is_closed станет True).
    assert mock_connection.close.call_count == 1
