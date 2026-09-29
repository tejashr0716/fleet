.PHONY: up down migrate seed sim test bench lint format clean

up:
	docker compose up -d timescaledb redis api worker reclaimer

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -c "import asyncio; from app.db import AsyncSessionLocal; from app.models.vehicle import Vehicle, VehicleType, VehicleStatus; async def s():\n    async with AsyncSessionLocal() as ses:\n        ses.add_all([Vehicle(plate=f'KA-01-FL-{i:04d}', label=f'Fleet #{i}', vehicle_type=VehicleType.CAR, status=VehicleStatus.ACTIVE) for i in range(1, 1001)])\n        await ses.commit()\nasyncio.run(s())"

sim:
	docker compose up -d simulator

test:
	pytest -v tests/

bench:
	python benchmark/ingest_load.py
	python benchmark/e2e_latency.py
	python benchmark/query_bench.py

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
