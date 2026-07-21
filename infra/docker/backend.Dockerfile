FROM python:3.14-slim

WORKDIR /srv/backend

COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

