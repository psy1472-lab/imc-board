FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/src /app/backend/src
COPY supabase/migrations /app/supabase/migrations

ENV PYTHONPATH=/app/backend/src
ENV PORT=8000
ENV DATA_DIR=/app/data

EXPOSE 8000

CMD uvicorn interfaces.api.main:app --host 0.0.0.0 --port ${PORT} --app-dir /app/backend/src
