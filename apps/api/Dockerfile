FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: build essentials for asyncpg wheels + ffmpeg/ffprobe for the
# Phase 2 media engine + OpenCV headless runtime libs (glib, libgomp).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates \
        ffmpeg libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python -m src.seed && uvicorn src.main:app --host 0.0.0.0 --port 8000"]