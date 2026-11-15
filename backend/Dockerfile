# AI Writing Coach — backend production image
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migration metadata.
COPY alembic.ini ./
COPY alembic ./alembic

# Run as a non-root user.
RUN useradd --create-home awc && chown -R awc:awc /app
USER awc

EXPOSE 8000

# Apply migrations, then serve. Single worker: the in-process rate limiter
# and background tasks assume one process (see docs/DEPLOYMENT.md).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
