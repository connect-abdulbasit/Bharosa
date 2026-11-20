# Bharosa developer commands. Uses a single venv at .venv for all Python folders.
PY := .venv/bin/python
export PYTHONPATH := $(CURDIR)

.PHONY: install dev test lint seed up down

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

seed:  ## TODO(Basit): seed demo users/cases into Postgres once models exist
	@echo "Demo users are currently seeded in memory (backend/app/auth/users.py). TODO(Basit): DB seed."

up:
	docker compose up --build

down:
	docker compose down
