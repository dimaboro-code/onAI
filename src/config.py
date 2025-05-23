import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация Redis и RabbitMQ
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
# REDIS_URL = "redis://localhost:6379" #  для локального запуска
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/dbname")
QUEUE_NAME = os.getenv("QUEUE_NAME", "task_queue")
APP_HOST = os.getenv("APP_HOST", 'localhost')
APP_PORT = int(os.getenv("APP_PORT", 8000))

# Ограничения
TIMES_TO_LIMIT = 10
SECONDS_TO_LIMIT = 60
MODEL_TOKENS_LIMIT = 4096
MODEL = os.getenv("MODEL", "gpt-4o-mini")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ваш_ключ_по_умолчанию")

LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", logging.DEBUG)


def setup_logger():
    """Конфигурация логгера."""
    logging.basicConfig(
        level=LOGGING_LEVEL,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("onAI")

    # Лог в файл
    file_handler = logging.FileHandler("onAI.log")
    file_handler.setLevel(LOGGING_LEVEL)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
