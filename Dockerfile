# Multi-stage production build: Python 3.12-slim
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

FROM python:3.12-slim AS runner

WORKDIR /workspace

RUN groupadd -r fleetgroup && useradd -r -g fleetgroup -d /workspace -s /sbin/nologin fleetuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app/ ./app/
COPY workers/ ./workers/
COPY simulator/ ./simulator/
COPY migrations/ ./migrations/
COPY alembic.ini .
COPY pyproject.toml .

RUN chown -R fleetuser:fleetgroup /workspace

USER fleetuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
