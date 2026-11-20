import pytest
from sqlalchemy import select

from app.models import AuditLog, Consent, ConsentEvent, User
from app.services import consent as consent_service
from tests.conftest import CITIZEN1, auth

CID = "con-%s-payments" % CITIZEN1


def audit_rows(db, action):
    return db.execute(select(AuditLog).where(AuditLog.action == action)).scalars().all()


def test_list_my_consents(client):
    items = client.get("/consent", headers=auth(client, "citizen")).json()["items"]
    assert {i["scope"] for i in items} == {"identity", "payments", "complaints", "notifications"}
    assert all(i["granted"] and i["citizen_id"] == CITIZEN1 for i in items)


def test_withdraw_then_require_fails_and_logs_blocked_attempt(client, db):
    h = auth(client, "citizen")
    r = client.post("/consent/%s/withdraw" % CID, json={"reason": "I do not trust this"}, headers=h)
    assert r.status_code == 200 and r.json()["granted"] is False and r.json()["withdrawn_at"]

    # event + audit for the withdrawal itself
    assert [e.action for e in db.execute(select(ConsentEvent).where(ConsentEvent.consent_id == CID)).scalars()][-1] == "withdraw"
    assert audit_rows(db, "consent.withdraw")[-1].after["reason"] == "I do not trust this"

    citizen = db.get(User, CITIZEN1)
    with pytest.raises(consent_service.ConsentRequired) as exc:
        consent_service.require(db, CITIZEN1, "payments", citizen, "ledger lookup")
    assert exc.value.scope == "payments"

    blocked = audit_rows(db, "consent.blocked")
    assert len(blocked) == 1 and blocked[0].actor_id == CITIZEN1 and blocked[0].after["scope"] == "payments"
    events = db.execute(select(ConsentEvent).where(ConsentEvent.consent_id == CID, ConsentEvent.action == "blocked")).scalars().all()
    assert len(events) == 1


def test_claim_blocked_after_withdrawal_returns_clear_403(client, db):
    h = auth(client, "citizen")
    assert client.post("/claims", json={"transcript": "x"}, headers=h).status_code == 200  # consent granted
    client.post("/consent/%s/withdraw" % CID, headers=h)
    r = client.post("/claims", json={"transcript": "x"}, headers=h)
    assert r.status_code == 403
    body = r.json()
    assert body["error"] == "consent_required" and body["scope"] == "payments" and "consent" in body["detail"].lower()
    assert len(audit_rows(db, "consent.blocked")) == 1  # persisted even though the request failed


def test_helper_blocked_when_citizen_withdrew(client, db):
    client.post("/consent/%s/withdraw" % CID, headers=auth(client, "citizen"))
    r = client.post("/claims", json={"on_behalf_of": CITIZEN1}, headers=auth(client, "helper"))
    assert r.status_code == 403 and r.json()["error"] == "consent_required"
    assert audit_rows(db, "consent.blocked")[-1].actor_id == "u-helper-1"


def test_grant_again_unblocks(client):
    h = auth(client, "citizen")
    client.post("/consent/%s/withdraw" % CID, headers=h)
    assert client.post("/claims", json={}, headers=h).status_code == 403
    g = client.post("/consent", json={"scope": "payments"}, headers=h)
    assert g.status_code == 200 and g.json()["granted"] is True
    assert client.post("/claims", json={}, headers=h).status_code == 200


def test_withdraw_twice_is_409_and_unknown_is_404(client):
    h = auth(client, "citizen")
    assert client.post("/consent/%s/withdraw" % CID, headers=h).status_code == 200
    assert client.post("/consent/%s/withdraw" % CID, headers=h).status_code == 409
    assert client.post("/consent/nope/withdraw", headers=h).status_code == 404


def test_cannot_withdraw_someone_elses_consent(client):
    other = "con-u-citizen-2-payments"
    assert client.post("/consent/%s/withdraw" % other, headers=auth(client, "citizen")).status_code == 404
    assert client.post("/consent/con-u-citizen-11-payments/withdraw", headers=auth(client, "helper")).status_code == 404


def test_correct_data_is_logged_with_before_after(client, db):
    h = auth(client, "citizen")
    r = client.post("/consent/%s/correct" % CID, json={"field": "name", "new_value": "Fatima Bibi Noor"}, headers=h)
    assert r.status_code == 200
    row = audit_rows(db, "consent.correct")[-1]
    assert row.before == {"name": "Fatima Bibi"} and row.after == {"name": "Fatima Bibi Noor"}
    assert db.get(User, CITIZEN1).name == "Fatima Bibi Noor"
    assert client.post("/consent/%s/correct" % CID, json={"field": "role", "new_value": "admin"}, headers=h).status_code == 422


def test_require_without_any_consent_row_blocks_and_logs(db):
    db.query(ConsentEvent).delete()
    db.query(Consent).filter(Consent.citizen_id == "u-citizen-5", Consent.scope == "complaints").delete()
    db.commit()
    with pytest.raises(consent_service.ConsentRequired):
        consent_service.require(db, "u-citizen-5", "complaints", None, "test")
    assert audit_rows(db, "consent.blocked")[-1].actor_type == "system"
