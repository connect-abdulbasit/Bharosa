from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_docs_available():
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_health_and_eval_show_the_ai_mode_per_function(client):
    from tests.conftest import auth

    names = {"classify_message", "match_person", "extract_claim", "read_document", "decide", "explain"}
    assert set(TestClient(app).get("/health").json()["ai_functions"]) == names
    r = client.get("/eval", headers=auth(client, "auditor"))
    assert r.status_code == 200 and set(r.json()["ai_functions"]) == names
