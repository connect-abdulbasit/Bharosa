"""Every role against every endpoint: allowed roles get 200, everyone else 403 (never 401/500)."""
import pytest

from tests.conftest import CITIZEN1, CITIZEN2, ROLES, auth

C1_CASE = "case-0004"  # citizen-1's case (status submitted), visible to citizen-1 and the helper
C1_IDENTITY_CONSENT = "con-%s-identity" % CITIZEN1


def helper_or_none(role, key="citizen_id", value=CITIZEN1):
    return {key: value} if role == "helper" else {}


# (method, path, body factory(role) -> dict|None, allowed roles)
ENDPOINTS = [
    ("GET", "/me", None, set(ROLES)),
    ("GET", "/cases", None, set(ROLES)),
    ("POST", "/cases", lambda r: dict(claim_type="missing", amount_claimed_pkr=12000, **helper_or_none(r)), {"citizen", "helper"}),
    ("GET", "/cases/" + C1_CASE, None, set(ROLES)),
    ("POST", "/cases/%s/assign" % C1_CASE, lambda r: {"officer_id": "u-officer-1"}, {"officer", "admin"}),
    ("POST", "/cases/%s/escalate" % C1_CASE, lambda r: {"reason": "family reports a middleman"}, {"helper", "officer"}),
    ("POST", "/cases/%s/decide" % C1_CASE, lambda r: {"action": "approve", "reason": "ledger checked"}, {"officer"}),
    ("POST", "/cases/%s/close" % C1_CASE, lambda r: {"resolution": "resolved"}, {"officer", "admin"}),
    ("POST", "/claims", lambda r: dict(helper_or_none(r, "on_behalf_of"), transcript="kam paise mile"), {"citizen", "helper"}),
    ("POST", "/messages/check", lambda r: {"text": "pay fee", "sender": "1234"}, {"citizen", "helper"}),
    ("POST", "/documents", lambda r: helper_or_none(r), {"citizen", "helper"}),
    ("GET", "/rules", None, {"officer", "admin", "auditor"}),
    ("GET", "/rules/rule-stipend-short-payment/versions", None, {"officer", "admin", "auditor"}),
    ("POST", "/rules/rule-stipend-short-payment/versions", lambda r: {"auto_handle_min": 0.95, "ask_more_min": 0.6}, {"admin"}),
    ("GET", "/consent", None, {"citizen", "helper"}),
    ("POST", "/consent", lambda r: dict(helper_or_none(r), scope="identity", **({"pin": "1234"} if r == "helper" else {})), {"citizen", "helper"}),
    ("POST", "/consent/%s/withdraw" % C1_IDENTITY_CONSENT, lambda r: {"reason": "changed my mind"}, {"citizen", "helper"}),
    ("POST", "/consent/%s/correct" % C1_IDENTITY_CONSENT, lambda r: {"field": "phone", "new_value": "03001234567"}, {"citizen", "helper"}),
    ("GET", "/audit", None, {"auditor", "admin"}),
    ("GET", "/queue", None, {"officer", "admin"}),
    ("GET", "/helper/families", None, {"helper"}),
    ("GET", "/apikeys", None, {"admin"}),
    ("POST", "/apikeys", lambda r: {"name": "partner", "scopes": ["cases:read"]}, {"admin"}),
    ("GET", "/eval", None, {"officer", "admin", "auditor"}),
    ("GET", "/public/cases/%s/status" % C1_CASE, None, set(ROLES)),
    ("POST", "/public/messages/check", lambda r: {"text": "pay fee", "sender": "1234"}, {"citizen", "helper", "officer", "admin"}),
]
IDS = ["%s %s" % (m, p) for m, p, *_ in ENDPOINTS]


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300


def call(client, method, path, body, headers):
    if path == "/documents":  # multipart upload
        return client.post(path, data=body or {}, files={"file": ("id.png", PNG, "image/png")}, headers=headers)
    return client.request(method, path, json=body, headers=headers)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS, ids=IDS)
def test_role_vs_endpoint(client, role, method, path, body, allowed):
    headers = auth(client, role)
    resp = call(client, method, path, body(role) if body else None, headers)
    if role in allowed:
        assert resp.status_code == (202 if path == "/claims" else 200), (role, method, path, resp.status_code, resp.text)
    else:
        assert resp.status_code == 403, (role, method, path, resp.status_code, resp.text)


@pytest.mark.parametrize("method,path,body,allowed", ENDPOINTS, ids=IDS)
def test_no_token_is_401(client, method, path, body, allowed):
    assert call(client, method, path, body("citizen") if body else None, {}).status_code == 401


def test_garbage_and_expired_tokens_are_401(client):
    import time

    import jwt

    from app.config import settings

    assert client.get("/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = jwt.encode({"sub": CITIZEN1, "role": "citizen", "exp": int(time.time()) - 10}, settings.JWT_SECRET, algorithm="HS256")
    assert client.get("/me", headers={"Authorization": "Bearer " + expired}).status_code == 401


def test_role_comes_from_database_not_token(client):
    """A token claiming role=admin for a citizen must not grant admin access."""
    import time

    import jwt

    from app.config import settings

    forged = jwt.encode({"sub": CITIZEN1, "role": "admin", "exp": int(time.time()) + 600}, settings.JWT_SECRET, algorithm="HS256")
    assert client.get("/audit", headers={"Authorization": "Bearer " + forged}).status_code == 403


def test_unknown_citizen2_listed_not_mixed(client):
    h = auth(client, "citizen")
    ids = [c["id"] for c in client.get("/cases", headers=h).json()["items"]]
    assert ids == [C1_CASE]
    assert CITIZEN2  # silence unused import in some linters
