import logging

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests.conftest import auth

ERROR_KEYS = {"error", "message", "request_id"}


def bad_login(client, **headers):
    return client.post("/auth/login", json={"username": "officer", "password": "wrong"}, headers=headers)


def test_login_is_rate_limited_with_a_clear_json_429(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", "3/minute")
    assert [bad_login(client).status_code for _ in range(3)] == [401, 401, 401]
    r = bad_login(client)
    assert r.status_code == 429
    body = r.json()
    assert set(body) == ERROR_KEYS and body["error"] == "rate_limited" and "Too many requests" in body["message"] and "3 per 1 minute" in body["message"]
    assert body["request_id"] == r.headers["X-Request-ID"] and r.headers["Retry-After"] == "60"
    ok = client.post("/auth/login", json={"username": "officer", "password": "officer-demo-123"})
    assert ok.status_code == 429  # even the right password waits: guessing must be slow


def test_forged_forwarded_for_header_does_not_dodge_the_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", "2/minute")
    monkeypatch.setattr(settings, "TRUST_PROXY", False)
    codes = [bad_login(client, **{"X-Forwarded-For": "10.0.0.%d" % i}).status_code for i in range(4)]
    assert codes == [401, 401, 429, 429]


def test_behind_a_trusted_proxy_each_client_ip_has_its_own_budget(client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT", "2/minute")
    monkeypatch.setattr(settings, "TRUST_PROXY", True)
    assert [bad_login(client, **{"X-Forwarded-For": "1.1.1.1"}).status_code for _ in range(3)] == [401, 401, 429]
    assert bad_login(client, **{"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}).status_code == 401  # a different real client


def test_normal_routes_have_a_default_limit_and_health_is_exempt(client, monkeypatch):
    h = auth(client, "citizen")
    monkeypatch.setattr(settings, "DEFAULT_RATE_LIMIT", "5/minute")
    codes = [client.get("/me", headers=h).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    assert all(client.get("/health").status_code == 200 for _ in range(10))


# ----------------------------------------------------------------------------- error format
def check_shape(r, status, error):
    assert r.status_code == status, r.text
    b = r.json()
    assert ERROR_KEYS <= set(b) and b["error"] == error and b["message"] and b["request_id"] == r.headers["X-Request-ID"], b
    return b


def test_404_401_403_409_have_the_same_shape(client):
    check_shape(client.get("/no/such/route"), 404, "not_found")
    check_shape(client.get("/cases/nope", headers=auth(client, "officer")), 404, "not_found")
    check_shape(client.get("/cases"), 401, "unauthorized")
    check_shape(client.get("/audit", headers=auth(client, "citizen")), 403, "forbidden")
    check_shape(client.post("/cases/case-0005/close", json={"resolution": "x"}, headers=auth(client, "officer")), 409, "conflict")
    check_shape(client.delete("/cases/case-0001", headers=auth(client, "officer")), 405, "method_not_allowed")
    b = check_shape(client.get("/audit", headers=auth(client, "citizen")), 403, "forbidden")
    assert set(b) == ERROR_KEYS  # nothing else leaks


def test_validation_errors_name_the_fields_and_never_echo_input(client):
    r = client.post("/cases", json={"claim_type": "missing", "amount_claimed_pkr": "SECRET-abc"}, headers=auth(client, "citizen"))
    b = check_shape(r, 422, "validation_error")
    assert [(f["in"], f["field"]) for f in b["fields"]] == [("body", "amount_claimed_pkr")] and b["fields"][0]["message"]
    assert "amount_claimed_pkr" in b["message"] and "SECRET-abc" not in r.text
    missing = client.post("/auth/login", json={})
    fields = {f["field"] for f in check_shape(missing, 422, "validation_error")["fields"]}
    assert fields == {"username", "password"}
    q = client.get("/audit", params={"limit": "lots"}, headers=auth(client, "admin"))
    assert check_shape(q, 422, "validation_error")["fields"][0]["in"] == "query"


def test_incoming_request_id_is_echoed_everywhere(client):
    r = client.get("/cases", headers={"X-Request-ID": "trace-me-42"})
    assert r.headers["X-Request-ID"] == "trace-me-42" and r.json()["request_id"] == "trace-me-42"


def test_unhandled_error_is_logged_in_full_but_never_leaked(client, monkeypatch, caplog):
    def explode(*a, **k):
        raise RuntimeError("secret internal detail: /etc/passwd password=hunter2")

    monkeypatch.setattr("app.routers.queue.latest_decision", explode)
    h = dict(auth(client, "officer"), **{"X-Request-ID": "boom-1"})
    safe = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="bharosa.error"):
        r = safe.get("/queue", headers=h)
    b = check_shape(r, 500, "internal_error")
    assert b["request_id"] == "boom-1" and "try again" in b["message"].lower()
    for leak in ("secret internal detail", "hunter2", "Traceback", "RuntimeError", "/etc/passwd", "queue.py"):
        assert leak not in r.text
    rec = [x for x in caplog.records if x.name == "bharosa.error"][0]
    assert rec.exc_info and "hunter2" in str(rec.exc_info[1]) and rec.request_id == "boom-1"  # the full error IS in the log


def test_consent_error_keeps_the_shape_with_extras(client):
    client.post("/consent/con-u-citizen-2-payments/withdraw", headers=auth(client, "helper"))
    r = client.post("/cases/case-0001/decide", json={"action": "approve", "reason": "approved by me"}, headers=auth(client, "officer"))
    b = check_shape(r, 403, "consent_required")
    assert b["scope"] == "payments" and b["citizen_id"] == "u-citizen-2"


def test_auditor_read_only_still_holds_on_the_new_public_write(client):
    """(the dedicated auditor file covers the full list; this guards the 403 shape too)"""
    r = client.post("/public/messages/check", json={"text": "x", "sender": "y"}, headers=auth(client, "auditor"))
    check_shape(r, 403, "forbidden")
    assert "read-only" in r.json()["message"]
