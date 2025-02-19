import pytest
from unittest.mock import patch, AsyncMock
from src.openai_service import get_answer
from src.config import MODEL  # Опционально, если нужно сверять точное имя модели


@pytest.mark.asyncio
async def test_get_answer_success():
    """
    Тест проверяет, что при успешном запросе к OpenAI
    возвращается нужный ответ (response.choices[0].message.content).
    """
    mock_response = AsyncMock()
    mock_response.choices[0].message.content = "Успешный ответ"
    with patch("src.openai_service.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        messages = [{"role": "user", "content": "Привет, как дела?"}]
        result = await get_answer(messages)
        assert result == "Успешный ответ"
        mock_create.assert_awaited_once_with(
            model=MODEL,
            messages=messages
        )


@pytest.mark.asyncio
async def test_get_answer_error():
    """
    Тест проверяет, что в случае любого исключения внутри get_answer
    метод возвращает "Ошибка при обработке запроса к OpenAI."
    """
    # Имитируем ошибку при вызове create()
    with patch("src.openai_service.client.chat.completions.create", side_effect=Exception("OpenAI Error")):
        messages = [{"role": "user", "content": "Привет, как дела?"}]
        result = await get_answer(messages)

        # Должен вернуться текст "Ошибка при обработке запроса к OpenAI."
        assert result == "Ошибка при обработке запроса к OpenAI."
