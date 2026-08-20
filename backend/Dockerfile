FROM python:3.11-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
