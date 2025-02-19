import httpx
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import Response

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import RABBITMQ_URL, QUEUE_NAME
from src.consumer import (
    get_messages_list_as_json,
    process_message,
    send_answer,
    callback,
    consume,
    Role,
)
from src.models import InputMessage
from src.database import DBMessage


@pytest.mark.asyncio
async def test_get_messages_list_as_json():
    """
    Проверяет преобразование списка DBMessage в формат, ожидаемый OpenAI API.
    """
    fake_db_messages = [
        DBMessage(id=1, content="Hello", role=Role.user),
        DBMessage(id=2, content="How can I help?", role=Role.assistant),
    ]
    result = get_messages_list_as_json(fake_db_messages)
    assert len(result) == 2
    assert result[0] == {"role": "user", "content": "Hello"}
    assert result[1] == {"role": "assistant", "content": "How can I help?"}


@pytest.mark.asyncio
async def test_process_message_success():
    """
    Проверяет, что process_message:
    1) сохраняет входящее сообщение (user) в БД,
    2) запрашивает всю историю,
    3) вызывает get_answer,
    4) сохраняет ответ (assistant) в БД,
    5) возвращает ответ.
    """
    input_msg = InputMessage(message="Hi there!", callback_url="http://example.com/")

    mock_insert_message = AsyncMock()
    mock_get_all_messages = AsyncMock()
    mock_get_all_messages.return_value = [
        DBMessage(id=1, content="Hello", role=Role.user),
        DBMessage(id=2, content="...", role=Role.assistant),
    ]

    mock_get_answer = AsyncMock(return_value="Mocked AI reply")

    with patch("src.consumer.insert_message", mock_insert_message), \
            patch("src.consumer.get_all_messages", mock_get_all_messages), \
            patch("src.consumer.get_answer", mock_get_answer):
        mock_session = AsyncMock(spec=AsyncSession)

        result = await process_message(mock_session, input_msg)

        mock_insert_message.assert_any_call(
            mock_session,
            input_msg.message,
            Role.user
        )
        mock_get_all_messages.assert_awaited_once_with(mock_session)

        mock_get_answer.assert_awaited_once()
        mock_insert_message.assert_any_call(mock_session, "Mocked AI reply", Role.assistant)

        assert result == "Mocked AI reply"


@pytest.mark.asyncio
async def test_send_answer_success():
    """
    Проверяем успешную отправку ответа через httpx.
    """
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(status_code=200, json={"ok": True})

        callback_url = "http://example.com/callback"
        answer_text = "Hello from AI"
        await send_answer(callback_url, answer_text)

        mock_post.assert_awaited_once_with(
            callback_url,
            json={"message": answer_text}
        )


@pytest.mark.asyncio
async def test_send_answer_failure():
    """
    Проверяем, что при ошибке в httpx внутри send_answer
    ошибку логируем, но исключение наружу не пробрасываем.
    """
    with patch("httpx.AsyncClient.post", side_effect=httpx.HTTPError("Network error")) as mock_post:
        callback_url = "http://example.com/callback"
        answer_text = "Hello from AI"

        await send_answer(callback_url, answer_text)
        mock_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_handles_process_message_failure():
    json_in = '{"message": "Hi from user", "callback_url": "http://callback.test/"}'
    mock_incoming = MagicMock()
    mock_incoming.body = json_in.encode("utf-8")

    mock_incoming.process.return_value.__aenter__.return_value = mock_incoming
    mock_incoming.process.return_value.__aexit__ = AsyncMock()

    with patch("src.consumer.process_message", new_callable=AsyncMock) as mock_proc_msg, \
            patch("src.consumer.send_answer", new_callable=AsyncMock) as mock_snd_ans, \
            patch("src.consumer.get_async_session", new_callable=MagicMock) as mock_get_session:
        mock_proc_msg.side_effect = Exception("Processing error")
        mock_get_session.return_value.__aenter__.return_value = mock_get_session
        mock_get_session.return_value.__aexit__ = AsyncMock()

        await callback(mock_incoming)

        mock_proc_msg.assert_awaited_once()
        mock_snd_ans.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_partial():
    """
    Проверка: вызывается ли declare_queue и consume при старте функции consume.
    Бесконечный цикл не тестируем напрямую,
    но проверяем, что базовая логика работает.
    """
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()

    with patch("src.consumer.create_tables", new_callable=AsyncMock) as mock_tables, \
            patch("aio_pika.connect_robust", return_value=mock_connection) as mock_connect:
        mock_connection.channel.return_value = mock_channel
        mock_channel.declare_queue.return_value = mock_queue

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(consume(), timeout=0.1)

        mock_tables.assert_awaited_once()

        mock_connect.assert_awaited_once_with(RABBITMQ_URL)
        mock_channel.declare_queue.assert_called_once_with(QUEUE_NAME, durable=True)
        mock_queue.consume.assert_awaited_once()
