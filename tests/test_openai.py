import pytest
from unittest.mock import patch, AsyncMock
from src.openai import get_answer
from src.config import MODEL  # Опционально, если нужно сверять точное имя модели


@pytest.mark.asyncio
async def test_get_answer_success():
    """
    Тест проверяет, что при успешном запросе к OpenAI
    возвращается нужный ответ (response.choices[0].message.content).
    """
    # Создаем поддельный объект ответа, у которого есть .choices с нужной структурой
    mock_response = AsyncMock()
    mock_response.choices = [
        # .message.content — по аналогии с вашей структурой в get_answer()
        type("Obj", (object,), {"message": type("Msg", (object,),
            {"content": "Успешный ответ"})()})
    ]

    # С помощью patch "перехватываем" вызов client.chat.completions.create
    # в вашем модуле и подставляем mock_response
    with patch("src.openai_service.client.chat.completions.create", return_value=mock_response) as mock_create:
        messages = [{"role": "user", "content": "Привет, как дела?"}]
        result = await get_answer(messages)

        # Проверяем, что вернули контент, который мы зашили в mock_response
        assert result == "Успешный ответ"

        # Проверяем, что create() был вызван один раз с правильными параметрами
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
