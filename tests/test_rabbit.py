import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from starlette.responses import Response

import aio_pika

from src.rabbit import RabbitMQService
from src.models import InputMessage


@pytest.mark.asyncio
async def test_connect_creates_new_connection_and_channel(mocker):
    """
    Проверяем, что при отсутствии активного _connection или при закрытом соединении,
    connect() создаёт новое соединение и канал, а затем декларирует очередь.
    """
    # Создаём фиктивные объекты соединения и канала
    mock_connection = AsyncMock(spec=aio_pika.RobustConnection)
    mock_connection.is_closed = True  # Имитируем закрытое соединение
    mock_channel = AsyncMock(spec=aio_pika.Channel)

    # Настраиваем connect_robust, чтобы он возвращал наш mock_connection
    mock_connect_robust = mocker.patch(
        "aio_pika.connect_robust",
        return_value=mock_connection
    )
    # Когда вызываем `mock_connection.channel()`, вернётся mock_channel
    mock_connection.channel.return_value = mock_channel

    service = RabbitMQService("amqp://fake-url", "fake-queue")

    # Вызываем метод, чтобы проверить логику переподключения
    channel = await service.connect()

    # Проверяем, что действительно было вызвано aio_pika.connect_robust()
    mock_connect_robust.assert_called_once_with("amqp://fake-url")
    # Проверяем, что мы вызвали channel(), а затем объявили очередь
    mock_connection.channel.assert_awaited_once()
    mock_channel.declare_queue.assert_awaited_once_with("fake-queue", durable=True)
    # Убедимся, что возвращаемый объект — это mock_channel (канал)
    assert channel == mock_channel


@pytest.mark.asyncio
async def test_connect_reuses_open_connection_and_channel(mocker):
    """
    Проверяем, что если соединение и канал уже открыты, новый канал не создаётся.
    """
    mock_connection = MagicMock(spec=aio_pika.RobustConnection)
    mock_connection.is_closed = False
    mock_channel = MagicMock(spec=aio_pika.Channel)
    mock_channel.is_closed = False

    service = RabbitMQService("amqp://fake-url", "fake-queue")
    service._connection = mock_connection
    service._channel = mock_channel

    # Подменяем connect_robust на случай, если всё же вызовется, но ожидаем, что нет
    mock_connect_robust = mocker.patch("aio_pika.connect_robust")

    channel = await service.connect()

    # Проверяем, что действительно не вызывалось создание нового соединения
    mock_connect_robust.assert_not_called()
    mock_connection.channel.assert_not_called()
    assert channel == mock_channel


@pytest.mark.asyncio
async def test_send_message_success(mocker):
    """
    Проверяем отправку сообщения в случае успеха.
    """
    service = RabbitMQService("amqp://fake-url", "fake-queue")

    # Настраиваем mock для connect(), возвращаем «подделанный» канал
    mock_channel = AsyncMock(spec=aio_pika.Channel)
    service.connect = AsyncMock(return_value=mock_channel)

    # Мокаем метод publish
    mock_publish = AsyncMock()
    mock_channel.default_exchange.publish = mock_publish

    test_message = InputMessage(message="Hello RabbitMQ!", callback_url="http://fake-callback")

    response = await service.send_message(test_message)

    # Убедимся, что в connect() мы сходили
    service.connect.assert_awaited_once()

    # Убедимся, что publish был вызван
    mock_publish.assert_awaited_once()

    # Проверяем, что возвращаемый объект - это именно объект Response со статусом 200
    assert isinstance(response, Response)
    assert response.status_code == 200
    assert "Сообщение отправлено" in response.body.decode("utf-8")


@pytest.mark.asyncio
async def test_send_message_failure(mocker):
    """
    Проверяем, что при ошибке в процессе публикации вызывается HTTPException (500).
    """
    service = RabbitMQService("amqp://fake-url", "fake-queue")

    # Настраиваем mock, чтобы connect() вернул «подделанный» канал,
    # но имитируем ошибку при publish()
    mock_channel = AsyncMock(spec=aio_pika.Channel)
    error_message = "publish error"

    async def raise_error(*args, **kwargs):
        raise RuntimeError(error_message)

    mock_channel.default_exchange.publish.side_effect = raise_error
    service.connect = AsyncMock(return_value=mock_channel)

    test_message = InputMessage(message="Broken RabbitMQ!", callback_url="http://fake-callback")

    with pytest.raises(HTTPException) as exc_info:
        await service.send_message(test_message)

    assert exc_info.value.status_code == 500
    assert "Ошибка RabbitMQ" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_close_connection(mocker):
    """
    Проверяем, что закрытие соединения действительно вызывает close()
    при открытом соединении, и не вызывает лишнего при уже закрытом.
    """
    service = RabbitMQService("amqp://fake-url", "fake-queue")

    mock_connection = AsyncMock(spec=aio_pika.RobustConnection)
    mock_connection.is_closed = False
    service._connection = mock_connection

    await service.close_connection()
    mock_connection.close.assert_awaited_once()

    # Попытка повторно закрыть
    await service.close_connection()
    # Повторно close() уже не вызовется (так как is_closed станет True).
    assert mock_connection.close.call_count == 1
