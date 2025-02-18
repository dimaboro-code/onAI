from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl

from src.config import MODEL_TOKENS_LIMIT


class InputMessage(BaseModel):
    """
    Входящее сообщение

    Атрибуты:
    message: Текст сообщения пользователя, максимальная длина зависит от GPT модели
    callback_url: URL для отправки ответа
    """
    message: Annotated[
        str,
        Field(title="Сообщение", description="Текст сообщения", max_length=MODEL_TOKENS_LIMIT)
    ]
    callback_url: Annotated[
        HttpUrl,
        Field(title="URL", description="URL для отправки ответа")
    ]
