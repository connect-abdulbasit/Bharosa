from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
