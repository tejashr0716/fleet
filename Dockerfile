FROM python:3.13-slim
WORKDIR /srv/fleet
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml README.md ./
COPY app ./app
COPY workers ./workers
COPY simulator ./simulator
COPY benchmark ./benchmark
RUN pip install --no-cache-dir . && useradd --create-home fleet
COPY static ./static
COPY migrations ./migrations
COPY alembic.ini ./
USER fleet
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
