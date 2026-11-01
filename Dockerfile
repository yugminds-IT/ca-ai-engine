FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# ROLE=worker runs the Celery worker; anything else runs the API.
CMD ["sh", "-c", "if [ \"$ROLE\" = worker ]; then exec celery -A workers.celery_app worker --loglevel=info --queues=tds --concurrency=4; else exec uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
