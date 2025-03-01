from fastapi import HTTPException

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from fastapi import status
from redis import Redis

import src.config as config
from src.producer import app, lifespan


def test_redis():
    """
     Проверяем, что Redis доступен по URL из конфига.
     Тесты дальше зависят от редиса, поэтому он первый.
    """
    r = Redis.from_url(config.REDIS_URL)
    assert r.ping() == True


@pytest.mark.asyncio
async def test_send_message_to_rabbitmq_success():
    """
    Проверяем успешную отправку сообщения в /webhook.
    Мокаем rabbitmq_service, чтобы не посылать реальные запросы.
    """
    with patch("src.producer.rabbitmq_service.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "Mocked OK"
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/webhook",
                    json={"message": "Hello Rabbit!", "callback_url": "http://test2"}
                )
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_to_rabbitmq_failure():
    """
    Проверяем, что при ошибке в send_message возвращается HTTP 500.
    """
    with patch("src.producer.rabbitmq_service.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = HTTPException(status_code=500, detail="Test Error")
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/webhook", json={"message": "Fail me...",
                                                               "callback_url": "http://test2"})

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_delete_dialog_data_success():
    """
    Тестируем эндпоинт /delete_dialog_data. Проверяем, что возвращается статус 200,
    а также что фактически вызывается delete_all_messages.
    """
    mock_session = MagicMock()
    mock_session.return_value.__aenter__.return_value = mock_session
    mock_session.return_value.__aexit__.return_value = None
    with patch("src.producer.delete_all_messages", new_callable=AsyncMock) as mock_delete_all, \
            patch("src.database.get_async_session", new_callable=mock_session):
        mock_delete_all.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/delete_dialog_data")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "✅ Данные диалога удалены"}
        mock_delete_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_dialog_data_failure():
    """
    Тестируем, что при ошибке в delete_all_messages эндпоинт вернёт HTTP 500.
    """
    with patch("src.producer.delete_all_messages", new_callable=AsyncMock) as mock_delete_all:
        mock_delete_all.side_effect = Exception("DB Error")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/delete_dialog_data")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Ошибка при удалении данных диалога"
