# Build from the repo ROOT:  docker build -f backend/Dockerfile .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app:/app/ai PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UPLOAD_DIR=/data/uploads
# dependencies first (cached until pyproject changes), source after
COPY ai ./ai
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --no-cache-dir ./ai "./backend[monitoring]"
COPY contracts ./contracts
COPY backend ./backend
RUN adduser --disabled-password --gecos "" app \
 && mkdir -p /data/uploads && chown -R app /data /app/backend
USER app
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"
CMD ["sh", "start.sh"]
