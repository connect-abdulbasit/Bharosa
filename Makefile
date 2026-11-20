# Bharosa developer commands. Uses a single venv at .venv for all Python folders.
PY := .venv/bin/python
export PYTHONPATH := $(CURDIR)

.PHONY: install dev test lint seed migrate db up down

install:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e "./ai[dev]" -e "./backend[dev]" -e "./mocks[dev]"

dev:  ## run mocks (8001) and backend (8000) locally; frontend: cd frontend && npm run dev
	@echo "Starting mocks on :8001 and backend on :8000 (Ctrl-C to stop)"
	cd mocks && ../$(PY) -m uvicorn app.main:app --port 8001 --reload & \
	cd backend && MOCKS_URL=http://localhost:8001 ../$(PY) -m uvicorn app.main:app --port 8000 --reload

test:
	cd ai && ../$(PY) -m pytest -q
	cd backend && ../$(PY) -m pytest -q
	cd mocks && ../$(PY) -m pytest -q

lint:
	$(PY) -m ruff check ai backend mocks contracts

db:  ## start only postgres (host port from POSTGRES_PORT, default 5432)
	docker compose up -d postgres

migrate:  ## apply Alembic migrations (needs DATABASE_URL, see .env.example)
	cd backend && ../$(PY) -m alembic upgrade head

seed:  ## create demo users, helper + 10 citizens, 5 cases, rule v1, consents (idempotent; --reset to wipe)
	cd backend && PYTHONPATH=..:../ai ../$(PY) -m app.seed $(ARGS)

up:
	docker compose up --build

down:
	docker compose down
