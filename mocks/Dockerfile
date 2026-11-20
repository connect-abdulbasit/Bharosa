# Build from repo root: docker build -f mocks/Dockerfile .
FROM python:3.11-slim
WORKDIR /srv/mocks
COPY mocks/pyproject.toml ./
RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.5"
COPY mocks/app ./app
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
