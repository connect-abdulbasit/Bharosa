#!/bin/sh
# Production start: migrate, optionally seed demo data, then serve. Used by the Dockerfile CMD (Render / Railway / compose).
set -e
alembic upgrade head
if [ "$SEED_ON_START" = "1" ]; then python -m app.seed; fi   # idempotent, FAKE demo data
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}" \
     --proxy-headers --forwarded-allow-ips "*" --no-access-log   # we write our own JSON access log
