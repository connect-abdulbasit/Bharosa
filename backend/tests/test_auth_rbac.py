import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import audit

client = TestClient(app)
ROLES = ["citizen", "helper", "officer", "admin", "auditor"]


def token(role: str) -> dict:
    r = client.post("/auth/login", json={"username": role, "password": settings.DEMO_PASSWORDS[role]})
    assert r.status_code == 200
    assert r.json()["role"] == role
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_login_wrong_password():
    assert client.post("/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401


@pytest.mark.parametrize("role", ROLES)
def test_me_for_each_role(role):
    assert client.get("/me", headers=token(role)).json()["role"] == role


def test_no_token_is_401_and_garbage_token_is_401():
    assert client.get("/cases").status_code == 401
    assert client.get("/cases", headers={"Authorization": "Bearer garbage"}).status_code == 401


@pytest.mark.parametrize("path,allowed", [
    ("/audit", {"auditor", "admin"}),
    ("/queue", {"officer", "admin"}),
    ("/helper/families", {"helper"}),
    ("/apikeys", {"admin"}),
    ("/rules", {"officer", "admin", "auditor"}),
    ("/consent", {"citizen", "helper"}),
    ("/eval", {"officer", "admin", "auditor"}),
])
def test_rbac_matrix(path, allowed):
    for role in ROLES:
        code = client.get(path, headers=token(role)).status_code
        assert code == (200 if role in allowed else 403), (path, role, code)


def test_only_officer_can_decide_case():
    for role in ROLES:
        code = client.post("/cases/case-0001/decide", json={"action": "approve"}, headers=token(role)).status_code
        assert code == (200 if role == "officer" else 403), role


def test_mutation_writes_audit_log():
    before = len(audit.ENTRIES)
    client.post("/consent/consent-003/withdraw", headers=token("citizen"))
    assert len(audit.ENTRIES) > before
    assert audit.ENTRIES[-1]["action"] == "consent.withdraw"
