FROM python:3.14-slim

WORKDIR /srv/backend

COPY backend/pyproject.toml backend/README.md backend/alembic.ini ./
COPY backend/app ./app
COPY backend/alembic ./alembic

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && python -m app.seed && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]

