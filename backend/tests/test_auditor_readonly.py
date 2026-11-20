import pytest

from app.models import Case, Consent
from tests.conftest import auth

WRITES = [
    ("POST", "/cases", {"claim_type": "missing", "amount_claimed_pkr": 1}),
    ("POST", "/cases/case-0001/assign", {"officer_id": "u-officer-1"}),
    ("POST", "/cases/case-0001/escalate", {"reason": "x"}),
    ("POST", "/cases/case-0001/decide", {"action": "approve", "reason": "x"}),
    ("POST", "/cases/case-0001/close", {"resolution": "x"}),
    ("POST", "/claims", {}),
    ("POST", "/messages/check", {"text": "x", "sender": "y"}),
    ("POST", "/documents", None),
    ("POST", "/rules/rule-stipend-short-payment/versions", {"auto_handle_min": 0.9, "ask_more_min": 0.5}),
    ("POST", "/consent", {"scope": "identity"}),
    ("POST", "/consent/con-u-citizen-1-identity/withdraw", {}),
    ("POST", "/apikeys", {"name": "x"}),
    ("PUT", "/cases/case-0001", {}),
    ("PATCH", "/cases/case-0001", {}),
    ("DELETE", "/cases/case-0001", None),
    ("DELETE", "/audit", None),
]


@pytest.mark.parametrize("method,path,body", WRITES)
def test_auditor_write_is_403(client, db, method, path, body):
    h = auth(client, "auditor")
    cases_before = db.query(Case).count()
    r = client.request(method, path, json=body, headers=h)
    # PUT/PATCH/DELETE routes do not exist at all (405); everything that does exist must say 403.
    assert r.status_code in ((403, 405) if method in ("PUT", "PATCH", "DELETE") else (403,)), (method, path, r.status_code)
    assert db.query(Case).count() == cases_before
    assert db.query(Consent).filter(Consent.status == "withdrawn").count() == 0


def test_auditor_can_read_cases_and_audit(client):
    h = auth(client, "auditor")
    assert client.get("/cases", headers=h).json()["total"] == 5
    assert client.get("/audit", headers=h).status_code == 200
