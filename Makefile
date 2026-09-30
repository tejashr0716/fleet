.PHONY: setup up down logs test lint migrate seed sim bench
setup:
	python scripts/setup.py
up:
	docker compose --profile demo up --build -d
down:
	docker compose --profile demo down
logs:
	docker compose logs -f api worker simulator
test:
	pytest -q
lint:
	ruff check . && ruff format --check .
migrate:
	alembic upgrade head
seed:
	python -m simulator.seed
sim:
	python -m simulator.run --url http://localhost:8000 --trigger-alerts
bench:
	python -m benchmark.ingest_load --url http://localhost:8000
