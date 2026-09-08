# Build context: backend/ (Railway Root Directory = backend)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY src /app/backend/src
COPY migrations /app/backend/migrations

ENV PYTHONPATH=/app/backend/src
ENV MIGRATIONS_DIR=/app/backend/migrations
ENV PORT=8000
ENV DATA_DIR=/app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn interfaces.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir /app/backend/src"]
