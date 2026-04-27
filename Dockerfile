FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# System deps for psycopg2-binary, pandas/numpy wheels, yfinance, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

# Northflank's HTTP health check should target /health (already implemented).
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
