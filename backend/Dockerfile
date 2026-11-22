# Build from the repo ROOT:  docker build -f backend/Dockerfile .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app:/app/ai PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UPLOAD_DIR=/data/uploads
# OCR for the ID photo (ai/bharosa_ai/ocr.py): the Tesseract binary with the English + Urdu language packs, about 60 MB
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-urd \
 && rm -rf /var/lib/apt/lists/*
# dependencies first (cached until pyproject changes), source after
COPY ai ./ai
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --no-cache-dir ./ai "./backend[monitoring]" "pytesseract>=0.3"
COPY contracts ./contracts
# evaluation numbers for GET /eval (synthetic data, offline, under a second). ai/eval/eval_results.json is git-ignored, so build it here
RUN AI_MODE=real python ai/eval/run_eval.py --no-chart > /dev/null
COPY backend ./backend
RUN sed -i 's/\r$//' /app/backend/start.sh \
 && adduser --disabled-password --gecos "" app \
 && mkdir -p /data/uploads && chown -R app /data /app/backend
USER app
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)"
CMD ["sh", "start.sh"]
