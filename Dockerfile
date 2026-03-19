FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.3.2 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock README.md /app/

RUN poetry install --only main --no-root

COPY app /app/app

EXPOSE 8000

ENV PORTCAST_DATABASE__URL=sqlite+pysqlite:////data/app.db

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

