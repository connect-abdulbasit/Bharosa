"""Walks EVERY route in the app (so a new route is covered automatically, or fails loudly) and checks the security promises:
 1. nothing is reachable without auth except /health and /auth/login (public routes need a JWT or a key);
 2. a citizen never gets 200 for another citizen's id (404 where the citizen may call it, 403 where the role is not allowed);
 3. an auditor gets 403 on every non-GET route;
 4. an API key opens ONLY the public routes."""
import re

import pytest
from fastapi.routing import APIRoute

from app.auth.deps import get_current_user
from app.main import app
from tests.conftest import auth, make_image

OPEN = {("GET", "/health"), ("POST", "/auth/login")}
PUBLIC = {("GET", "/public/cases/{case_id}/status"), ("POST", "/public/messages/check")}
EXPECT_404 = {("GET", "/cases/{case_id}"), ("GET", "/claims/{claim_id}"), ("GET", "/claims/{claim_id}/progress"),
              ("POST", "/claims/{claim_id}/resume"), ("GET", "/documents/{document_id}/image"), ("POST", "/consent/{consent_id}/withdraw"),
              ("POST", "/consent/{consent_id}/correct"), ("GET", "/public/cases/{case_id}/status")}
EXPECT_403 = {("POST", "/cases/{case_id}/assign"), ("POST", "/cases/{case_id}/escalate"), ("POST", "/cases/{case_id}/decide"),
              ("POST", "/cases/{case_id}/close"), ("POST", "/apikeys/{key_id}/revoke"), ("GET", "/rules/{rule_id}/versions"),
              ("POST", "/rules/{rule_id}/versions"), ("POST", "/rules/{rule_id}/simulate")}
BODIES = {("POST", "/consent/{consent_id}/correct"): {"field": "phone", "new_value": "03001112222"}}


def all_routes():
    out = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path, r))
    return out


def fill(path, ids):
    return re.sub(r"\{(\w+)\}", lambda m: ids.get(m.group(1), "x"), path)


def has_auth(dependant) -> bool:
    for d in dependant.dependencies:
        name = getattr(d.call, "__qualname__", "")
        if d.call is get_current_user or name.startswith("public_access"):
            return True
        if has_auth(d):
            return True
    return False


def test_the_walk_actually_finds_the_routes():
    routes = all_routes()
    assert len(routes) >= 35
    paths = {(m, p) for m, p, _ in routes}
    assert OPEN <= paths and PUBLIC <= paths and EXPECT_404 <= paths and EXPECT_403 <= paths


def test_every_route_declares_authentication():
    missing = [(m, p) for m, p, r in all_routes() if (m, p) not in OPEN and not has_auth(r.dependant)]
    assert missing == []  # a new route without require_role / public_access fails here


def test_nothing_is_reachable_without_credentials(client):
    leaks = []
    for m, p, _ in all_routes():
        if (m, p) in OPEN:
            continue
        r = client.request(m, fill(p, {}), json={} if m != "GET" else None)
        if r.status_code != 401:
            leaks.append((m, p, r.status_code))
    assert leaks == []
    assert client.get("/health").status_code == 200
    assert client.post("/auth/login", json={"username": "officer", "password": "wrong"}).status_code == 401  # reachable, but refuses


def test_garbage_credentials_are_no_better_than_none(client):
    for m, p, _ in all_routes():
        if (m, p) in OPEN:
            continue
        for h in ({"Authorization": "Bearer not.a.jwt"}, {"X-API-Key": "bhr_live_nope"}):
            assert client.request(m, fill(p, {}), json={} if m != "GET" else None, headers=h).status_code == 401, (m, p, h)


@pytest.fixture()
def ids(client):
    """Real ids that belong to citizen02 (u-citizen-2), plus fixed ones for case/consent/rule."""
    h = auth(client, "citizen02")
    doc = client.post("/documents", files={"file": ("a.jpg", make_image(300, 200, "JPEG"), "image/jpeg")}, headers=h).json()["document_id"]
    claim = client.post("/claims", json={"transcript": "mujhe is mahine ke paisay nahi mile"}, headers=h).json()["claim_id"]
    return {"case_id": "case-0001", "claim_id": claim, "document_id": doc, "consent_id": "con-u-citizen-2-identity",
            "rule_id": "rule-stipend-short-payment", "key_id": "some-key"}


def test_a_citizen_never_gets_another_citizens_ids(client, ids, db):
    routes = {(m, p) for m, p, _ in all_routes() if "{" in p}
    assert routes == EXPECT_404 | EXPECT_403  # a new id route must be added to one of the two sets (and thought about)
    h = auth(client, "citizen")  # u-citizen-1 owns none of these
    for m, p in sorted(routes):
        r = client.request(m, fill(p, ids), json=BODIES.get((m, p), {}) if m != "GET" else None, headers=h)
        want = 404 if (m, p) in EXPECT_404 else 403
        assert r.status_code == want, (m, p, r.status_code, r.text)
        assert r.status_code != 200
    from app.models import Consent, User

    db.expire_all()
    assert db.get(Consent, "con-u-citizen-2-identity").status == "granted" and db.get(User, "u-citizen-2").phone != "03001112222"  # nothing changed


def test_an_unlinked_helper_gets_404_for_the_same_ids_too(client, ids):
    # u-citizen-11 is not linked to the helper; its case is case-0005
    h = auth(client, "helper")
    assert client.get("/cases/case-0005", headers=h).status_code == 404
    doc = client.post("/documents", files={"file": ("a.jpg", make_image(300, 200, "JPEG"), "image/jpeg")}, headers=auth(client, "citizen11")).json()["document_id"]
    assert client.get("/documents/%s/image" % doc, headers=h).status_code == 404
    assert client.post("/consent/con-u-citizen-11-identity/withdraw", headers=h).status_code == 404


def test_an_auditor_is_forbidden_on_every_non_get_route(client, ids, db):
    h = auth(client, "auditor")
    tested = 0
    from app.models import Case, Consent

    cases, withdrawn = db.query(Case).count(), db.query(Consent).filter(Consent.status == "withdrawn").count()
    for m, p, _ in all_routes():
        if m == "GET" or (m, p) in OPEN:
            continue
        r = client.request(m, fill(p, ids), json={}, headers=h)
        assert r.status_code == 403, (m, p, r.status_code)
        tested += 1
    assert tested >= 20
    db.expire_all()
    assert db.query(Case).count() == cases and db.query(Consent).filter(Consent.status == "withdrawn").count() == withdrawn
    for p in ("/me", "/cases", "/audit", "/rules", "/eval", "/scam-map"):  # read-only, not blind
        assert client.get(p, headers=h).status_code == 200, p


def test_an_api_key_opens_only_the_public_routes(client, ids):
    key = client.post("/apikeys", json={"name": "k", "scopes": ["cases:read", "messages:check"]}, headers=auth(client, "admin")).json()["key"]
    k = {"X-API-Key": key}
    for m, p, _ in all_routes():
        if (m, p) in OPEN or (m, p) in PUBLIC:
            continue
        r = client.request(m, fill(p, ids), json={} if m != "GET" else None, headers=k)
        assert r.status_code == 401, (m, p, r.status_code)
    assert client.get("/public/cases/case-0001/status", headers=k).status_code == 200
    assert client.post("/public/messages/check", json={"text": "hi", "sender": "9090"}, headers=k).status_code == 200


def test_error_bodies_never_leak_internals(client, ids):
    h = auth(client, "citizen")
    for m, p, _ in all_routes():
        if (m, p) in OPEN:
            continue
        r = client.request(m, fill(p, ids), json={} if m != "GET" else None, headers=h)
        assert r.status_code < 500, (m, p, r.status_code)
        text = r.text
        for leak in ("Traceback", "sqlalchemy", "psycopg", ".py", "sqlite"):
            assert leak not in text, (m, p, leak)
