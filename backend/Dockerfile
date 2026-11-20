# Build from repo root: docker build -f backend/Dockerfile .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app:/app/ai PYTHONUNBUFFERED=1
COPY contracts ./contracts
COPY ai ./ai
COPY backend ./backend
RUN pip install --no-cache-dir ./ai ./backend
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && if [ \"$SEED_ON_START\" = \"1\" ]; then python -m app.seed; fi && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
