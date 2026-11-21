import hashlib

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import ApiKey, AuditLog
from tests.conftest import auth

SCAM = {"text": "Pay fee at http://bit.ly/x to get your relief money urgent", "sender": "SAHARA-INFO"}


def make_key(client, scopes=("cases:read", "messages:check"), name="Partner NGO"):
    r = client.post("/apikeys", json={"name": name, "scopes": list(scopes)}, headers=auth(client, "admin"))
    assert r.status_code == 200, r.text
    return r.json()


def K(key):
    return {"X-API-Key": key}


def test_key_is_shown_once_and_only_a_hash_is_stored(client, db):
    created = make_key(client)
    key = created["key"]
    assert key.startswith("bhr_live_") and created["prefix"] == key[:13] and created["revoked"] is False
    row = db.query(ApiKey).one()
    assert row.key_hash == hashlib.sha256(key.encode()).hexdigest() and key not in (row.key_hash, row.prefix)
    listing = client.get("/apikeys", headers=auth(client, "admin"))
    assert key not in listing.text and "key_hash" not in listing.text and listing.json()["items"][0]["prefix"] == key[:13]


@pytest.mark.parametrize("scopes", [[], ["cases:write"], ["cases:read", "admin:all"]])
def test_bad_scopes_are_rejected(client, scopes):
    r = client.post("/apikeys", json={"name": "x", "scopes": scopes}, headers=auth(client, "admin"))
    assert r.status_code == 422 and "scopes" in r.json()["message"]


def test_only_admins_manage_keys(client):
    for who in ("citizen", "helper", "officer", "auditor"):
        h = auth(client, who)
        assert client.post("/apikeys", json={"name": "x", "scopes": ["cases:read"]}, headers=h).status_code == 403
        assert client.get("/apikeys", headers=h).status_code == 403


def test_status_with_a_key_is_minimal(client, mocks):
    key = make_key(client)["key"]
    r = client.get("/public/cases/case-0001/status", headers=K(key))
    assert r.status_code == 200
    assert set(r.json()) == {"case_id", "status", "current_step", "updated_at"} and r.json()["status"] == "with_officer"
    assert "Aslam" not in r.text and "amount" not in r.text  # no personal data
    assert client.get("/public/cases/nope/status", headers=K(key)).status_code == 404


def test_message_check_with_a_key(client, mocks):
    key = make_key(client)["key"]
    r = client.post("/public/messages/check", json=dict(SCAM, area="Malir"), headers=K(key))
    assert r.status_code == 200 and r.json()["label"] == "scam" and r.json()["reasons"] and r.json()["explanation_ur"]


def test_scopes_are_enforced_and_denials_audited(client, db, mocks):
    only_check = make_key(client, ["messages:check"], "checker")["key"]
    only_read = make_key(client, ["cases:read"], "reader")["key"]
    assert client.get("/public/cases/case-0001/status", headers=K(only_check)).status_code == 403
    assert client.post("/public/messages/check", json=SCAM, headers=K(only_read)).status_code == 403
    assert client.get("/public/cases/case-0001/status", headers=K(only_read)).status_code == 200
    denied = db.execute(select(AuditLog).where(AuditLog.action == "apikey.denied")).scalars().all()
    assert len(denied) == 2 and {d.after["reason"] for d in denied} == {"cases:read", "messages:check"}


def test_invalid_missing_and_revoked_keys(client, db):
    assert client.get("/public/cases/case-0001/status", headers=K("bhr_live_not-a-real-key")).status_code == 401
    assert client.get("/public/cases/case-0001/status").status_code == 401
    created = make_key(client)
    admin = auth(client, "admin")
    assert client.get("/public/cases/case-0001/status", headers=K(created["key"])).status_code == 200
    r = client.post("/apikeys/%s/revoke" % created["id"], headers=admin)
    assert r.status_code == 200 and r.json()["revoked"] is True
    assert client.get("/public/cases/case-0001/status", headers=K(created["key"])).status_code == 401  # effective immediately
    assert client.post("/apikeys/%s/revoke" % created["id"], headers=admin).status_code == 409
    assert client.post("/apikeys/nope/revoke", headers=admin).status_code == 404
    assert client.post("/apikeys/%s/revoke" % created["id"], headers=auth(client, "officer")).status_code == 403
    bad = db.execute(select(AuditLog).where(AuditLog.action == "apikey.denied")).scalars().all()
    assert len(bad) == 2 and "bhr_live_not-a-real-key" not in str([b.after for b in bad])  # only a short prefix is logged
    assert db.execute(select(AuditLog).where(AuditLog.action == "apikey.revoke")).scalars().one().before == {"active": True}


def test_every_use_is_audited_and_last_used_is_updated(client, db, mocks):
    created = make_key(client)
    key = created["key"]
    assert client.get("/apikeys", headers=auth(client, "admin")).json()["items"][0].get("last_used_at") is None
    client.get("/public/cases/case-0001/status", headers=K(key))
    client.post("/public/messages/check", json=SCAM, headers=K(key))
    uses = db.execute(select(AuditLog).where(AuditLog.action == "apikey.use").order_by(AuditLog.id)).scalars().all()
    assert len(uses) == 2 and all(u.actor_type == "system" and u.actor_id == created["id"] for u in uses)
    assert uses[0].after["path"] == "/public/cases/case-0001/status" and uses[0].after["scope"] == "cases:read" and uses[0].after["method"] == "GET"
    assert uses[1].after["scope"] == "messages:check" and uses[1].request_id
    assert client.get("/apikeys", headers=auth(client, "admin")).json()["items"][0]["last_used_at"]


def test_a_key_cannot_reach_private_routes(client, mocks):
    key = make_key(client)["key"]
    for method, path in (("GET", "/cases"), ("GET", "/queue"), ("GET", "/audit"), ("GET", "/apikeys"), ("POST", "/messages/check"), ("POST", "/claims")):
        r = client.request(method, path, headers=K(key), json={} if method == "POST" else None)
        assert r.status_code == 401, (path, r.status_code)  # only JWTs open the private API


def test_jwt_works_on_public_routes_with_normal_rules(client, mocks):
    c = auth(client, "citizen")
    assert client.get("/public/cases/case-0004/status", headers=c).status_code == 200      # own case
    assert client.get("/public/cases/case-0001/status", headers=c).status_code == 404      # someone else's
    assert client.get("/public/cases/case-0001/status", headers=auth(client, "officer")).status_code == 200
    assert client.post("/public/messages/check", json=SCAM, headers=c).status_code == 200
    assert client.post("/public/messages/check", json=SCAM, headers=auth(client, "auditor")).status_code == 403  # read-only


def test_per_key_rate_limit(client, mocks, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_RATE_LIMIT", "3/minute")
    a, b = make_key(client, name="a")["key"], make_key(client, name="b")["key"]
    for _ in range(3):
        assert client.get("/public/cases/case-0001/status", headers=K(a)).status_code == 200
    r = client.get("/public/cases/case-0001/status", headers=K(a))
    assert r.status_code == 429 and r.json()["error"] == "rate_limited" and r.headers["Retry-After"]
    assert client.get("/public/cases/case-0001/status", headers=K(b)).status_code == 200  # another key has its own budget
