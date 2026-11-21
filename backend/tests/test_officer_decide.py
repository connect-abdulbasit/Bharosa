from sqlalchemy import select

from app.models import AuditLog, Case, Decision
from tests.conftest import auth


def decide(client, case, body, who="officer"):
    return client.post("/cases/%s/decide" % case, json=body, headers=auth(client, who))


def test_reason_is_required(client):
    for body in ({"action": "approve"}, {"action": "approve", "reason": ""}, {"action": "approve", "reason": "  "},
                 {"action": "approve", "reason": "x"}, {"action": "reject", "note": None}):
        r = decide(client, "case-0001", body)
        assert r.status_code == 422, body
        assert "reason" in r.json()["message"].lower()
    assert client.get("/cases/case-0001", headers=auth(client, "officer")).json()["status"] == "with_officer"  # untouched
    assert decide(client, "case-0001", {"action": "reject", "note": "ledger matches what she received"}).status_code == 200  # `note` counts


def test_citizen_helper_admin_auditor_cannot_decide(client):
    for who in ("citizen", "helper", "admin", "auditor"):
        assert decide(client, "case-0001", {"action": "approve", "reason": "please"}, who).status_code == 403, who


def test_unknown_action_is_422(client):
    assert decide(client, "case-0001", {"action": "pay_everyone", "reason": "because"}).status_code == 422


def test_approve_releases_the_payment_and_records_everything(client, db, mocks):
    r = decide(client, "case-0001", {"action": "approve", "reason": "Ledger shows PKR 8000 of 12000, topping up the rest"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    d = r.json()["decision"]
    assert d["decided_by"] == "u-officer-1" and d["action"] == "approve" and d["rule_version"] == 1
    pay = d["trace"]["payment"]
    assert pay["payment_ref"] == "PAY-TEST0001" and pay["amount_pkr"] == 4000 and pay["simulated"] is True
    assert pay["idempotency_key"] == "case-0001:%s" % d["id"]
    assert any("Payment released: PKR 4000" in n["text"] for n in r.json()["notes"])
    assert mocks.calls == ["disburse"]
    row = db.execute(select(Decision).where(Decision.case_id == "case-0001").order_by(Decision.created_at.desc())).scalars().first()
    assert row.decided_by == "u-officer-1" and row.rule_id == "rule-stipend-short-payment" and row.reasons[0].startswith("Ledger shows")
    assert row.payment_ref == "PAY-TEST0001" and row.payment_status == "paid" and row.idempotency_key == "case-0001:%s" % row.id
    actions = [a.action for a in db.execute(select(AuditLog).where(AuditLog.entity_id == "case-0001")).scalars()]
    assert "payment.release" in actions and "case.decide" in actions


def test_reject_makes_no_payment(client, mocks):
    r = decide(client, "case-0001", {"action": "reject", "reason": "Payment record is correct"})
    assert r.json()["status"] == "rejected" and mocks.calls == [] and r.json()["decision"]["trace"]["payment"] is None


def test_payment_failure_changes_nothing_and_is_not_a_500(client, db, mocks):
    mocks.fail = {"disburse"}
    r = decide(client, "case-0001", {"action": "approve", "reason": "approved by me"})
    assert r.status_code == 503 and "payment could not be released" in r.json()["message"].lower()
    assert db.get(Case, "case-0001").status == "with_officer"
    assert db.execute(select(AuditLog).where(AuditLog.action == "payment.failed")).scalars().first() is not None
    mocks.fail = set()
    assert decide(client, "case-0001", {"action": "approve", "reason": "retry worked"}).status_code == 200


def test_payment_blocked_when_complaints_consent_withdrawn(client, db, mocks):
    client.post("/consent/con-u-citizen-2-payments/withdraw", headers=auth(client, "helper"))  # a linked helper may withdraw
    r = decide(client, "case-0001", {"action": "approve", "reason": "approved by me"})
    assert r.status_code == 403 and r.json()["error"] == "consent_required" and r.json()["scope"] == "payments"
    assert db.get(Case, "case-0001").status == "with_officer" and mocks.calls == []
    assert db.execute(select(AuditLog).where(AuditLog.action == "consent.blocked")).scalars().first() is not None


def test_ask_more_and_alias(client):
    r = decide(client, "case-0001", {"action": "ask_more", "reason": "need a clearer ID photo"})
    assert r.json()["status"] == "needs_more_proof" and r.json()["decision"]["action"] == "ask_more"
    assert decide(client, "case-0001", {"action": "request_more", "reason": "still blurry"}).json()["status"] == "needs_more_proof"


def test_cannot_decide_a_closed_case(client):
    assert decide(client, "case-0005", {"action": "approve", "reason": "again please"}).status_code == 409
