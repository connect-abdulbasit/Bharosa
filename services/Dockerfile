# Notifications + webhooks + job log (simulated). Build from the repo ROOT:  docker build -f services/Dockerfile .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.5" "httpx>=0.27"
COPY services ./services
RUN adduser --disabled-password --gecos "" app
USER app
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8002'), timeout=4)"
CMD ["sh", "-c", "uvicorn services.main:app --host 0.0.0.0 --port ${PORT:-8002}"]
