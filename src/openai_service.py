from openai import AsyncOpenAI
from src.config import MODEL, OPENAI_API_KEY, logger

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def get_answer(json_messages: list[dict]) -> str:
    """
    Получает ответ на последнее сообщение из OpenAI.

    Args:
        json_messages (list[dict]): История сообщений в формате OpenAI API.

    Returns:
        str: Ответ модели.
    """
    try:
        logger.info("🔄 Отправка запроса в OpenAI...")
        response = await client.chat.completions.create(
            model=MODEL,
            messages=json_messages,
        )
        answer: str = response.choices[0].message.content
        logger.info("✅ Ответ от OpenAI получен")
        logger.debug(f"📜 Ответ: {answer}")
        return answer
    except Exception as e:
        logger.exception("❌ Ошибка запроса к OpenAI:", exc_info=e)
        return "Ошибка при обработке запроса к OpenAI."
