FROM python:3.12-slim
LABEL authors="dimaboro"
RUN pip install --no-cache-dir poetry
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-root
COPY . /app
ARG SCRIPT=producer.py
CMD ["poetry", "run", "python", "src/producer.py"]