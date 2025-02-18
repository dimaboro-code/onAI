import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from fastapi import status

from src.producer import app


@pytest.mark.asyncio
async def test_send_message_to_rabbitmq_success():
    """
    Проверяем успешную отправку сообщения в /webhook.
    Мокаем rabbitmq_service, чтобы не посылать реальные запросы.
    """
    # Подделываем метод send_message у rabbitmq_service, чтобы вернуть "фейковый" успех.
    with patch("app.rabbitmq_service.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "Mocked OK"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/webhook",
                json={"message": "Hello Rabbit!", "callback_url": "http://test2"}
            )
        # Убеждаемся, что запрос отработал без ошибок
        assert response.status_code == status.HTTP_200_OK
        # Проверяем, что реально вызывался send_message
        mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_to_rabbitmq_failure():
    """
    Проверяем, что при ошибке в send_message возвращается HTTP 500.
    """
    with patch("app.rabbitmq_service.send_message", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = Exception("Test error")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/webhook", json={"message": "Fail me...",
                                                           "callback_url": "http://test2"})

        # Ожидаем 500 Internal Server Error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.asyncio
async def test_delete_dialog_data_success():
    """
    Тестируем эндпоинт /delete_dialog_data. Проверяем, что возвращается статус 200,
    а также что фактически вызывается delete_all_messages.
    """
    with patch("app.delete_all_messages", new_callable=AsyncMock) as mock_delete_all:
        # Подделка, чтобы не идти в реальную базу
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
    with patch("app.delete_all_messages", new_callable=AsyncMock) as mock_delete_all:
        mock_delete_all.side_effect = Exception("DB Error")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/delete_dialog_data")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Ошибка при удалении данных диалога"
