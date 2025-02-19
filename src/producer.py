import redis.asyncio as redis
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from starlette.responses import JSONResponse

from src.config import TIMES_TO_LIMIT, SECONDS_TO_LIMIT, REDIS_URL, logger, APP_PORT, APP_HOST
from src.rabbit import rabbitmq_service
from src.models import InputMessage
from src.database import delete_all_messages, get_async_session


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Подключается к Redis, инициализирует FastAPI-limiter, а по завершении работы
    приложения корректно закрывает соединение с Redis и RabbitMQ.
    """
    try:
        logger.info("🔄 Подключение к Redis...")
        redis_connection = redis.from_url(
            REDIS_URL,
            encoding="utf8",
            decode_responses=True
        )
        await FastAPILimiter.init(redis_connection)
        logger.info("✅ Успешное подключение к Redis")
    except Exception as exc:
        logger.exception("❌ Ошибка при инициализации Redis:", exc_info=exc)
        raise HTTPException(status_code=500, detail="Ошибка подключения к Redis")

    yield

    logger.info("🔄 Закрытие соединений...")
    # Закрытие Redis и RabbitMQ
    try:
        await FastAPILimiter.close()
        logger.info("✅ Соединение с Redis закрыто")
    except Exception as exc:
        logger.exception("❌ Ошибка при закрытии соединения с Redis:", exc_info=exc)

    try:
        await rabbitmq_service.close_connection()
        logger.info("✅ Соединение с RabbitMQ закрыто")
    except Exception as exc:
        logger.exception("❌ Ошибка при закрытии соединения с RabbitMQ:", exc_info=exc)


app = FastAPI(lifespan=lifespan)


@app.post(
    "/webhook",
    dependencies=[Depends(RateLimiter(times=TIMES_TO_LIMIT, seconds=SECONDS_TO_LIMIT))]
)
async def send_message_to_rabbitmq(message: InputMessage):
    """
    Обрабатывает входящее сообщение и отправляет его в очередь RabbitMQ.
    Ограничения на частоту запросов задаются через RateLimiter.
    """
    logger.info("📩 Получено новое сообщение")
    logger.debug(f"📜 Содержимое сообщения: {message.model_dump_json()}")
    response = await rabbitmq_service.send_message(message)
    return response


@app.get("/delete_dialog_data")
async def delete_dialog_data(session=Depends(get_async_session)):
    """
    Удаляет все сообщения (данные диалога) в базе данных.
    """
    logger.info("🗑 Удаление данных диалога")
    try:
        await delete_all_messages(session)
        message = "✅ Данные диалога удалены"
        logger.info(message)
        return JSONResponse(status_code=200, content={"message": message})
    except Exception as exc:
        logger.exception("❌ Ошибка при удалении данных диалога:", exc_info=exc)
        raise HTTPException(status_code=500, detail="Ошибка при удалении данных диалога")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
