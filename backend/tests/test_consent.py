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


CLAIM = {"transcript": "mujhe is mahine ke paisay nahi mile"}
PAY5 = "con-u-citizen-5-payments"  # citizen05 (Mohammad Rafiq) has no open claim yet


def test_claim_after_withdrawal_pauses_with_officer_and_logs_blocked(client, db, mocks):
    """Missing consent never becomes a 500 or a silent skip: progress is saved, an officer is told exactly why."""
    h = auth(client, "citizen05")
    client.post("/consent/%s/withdraw" % PAY5, headers=h)
    r = client.post("/claims", json=CLAIM, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "with_officer"
    failed = [s for s in body["pipeline_steps"] if s["status"] == "failed"]
    assert failed and failed[0]["step"] == "ledger_lookup" and "payments" in failed[0]["detail"]
    assert len(audit_rows(db, "consent.blocked")) == 1  # persisted even though the step stopped
    assert "ledger" not in mocks.calls


def test_helper_claim_blocked_when_citizen_withdrew(client, db, mocks):
    client.post("/consent/%s/withdraw" % PAY5, headers=auth(client, "citizen05"))
    r = client.post("/claims", json=dict(CLAIM, on_behalf_of="u-citizen-5"), headers=auth(client, "helper"))
    assert r.status_code == 200 and r.json()["status"] == "with_officer"
    assert audit_rows(db, "consent.blocked")[-1].actor_id == "u-helper-1"


def test_grant_again_then_resume_completes(client, mocks):
    h = auth(client, "citizen05")
    client.post("/consent/%s/withdraw" % PAY5, headers=h)
    first = client.post("/claims", json=CLAIM, headers=h).json()
    assert first["status"] == "with_officer"
    g = client.post("/consent", json={"scope": "payments"}, headers=h)
    assert g.status_code == 200 and g.json()["granted"] is True
    again = client.post("/claims/%s/resume" % first["claim_id"], headers=h).json()
    assert [s["status"] for s in again["pipeline_steps"]].count("done") == 8 and again["status"] == "needs_more_proof"


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
