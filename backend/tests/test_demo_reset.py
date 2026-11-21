from sqlalchemy import func, select

import bharosa_ai  # noqa: F401
from app import demo as demo_mod
from app.config import settings
from app.fake_mocks_client import CHAOS, PAYMENTS
from app.models import (ApiKey, AuditLog, Case, CheckedMessage, Claim, Consent, ConsentEvent, Decision, Document, DocumentBlob, Job,
                        Rule, RuleVersion, User)
from tests.conftest import auth, make_image

SAY = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def reset(client, who="admin", **body):
    return client.post("/admin/demo/reset", json=body, headers=auth(client, who))


def make_a_mess(client, db):
    """Everything a demo day can change: claims, photos, consent, corrections, decisions, payments, scam checks, rule versions, outages."""
    c = auth(client, "s1-clean")
    client.post("/documents", files={"file": ("a.jpg", make_image(300, 200, "JPEG"), "image/jpeg")}, headers=c)
    client.post("/claims", json=SAY, headers=c)
    client.post("/claims", json=SAY, headers=auth(client, "s3-shortpay"))
    client.post("/consent/con-u-demo-1-identity/withdraw", json={"reason": "no"}, headers=c)
    client.post("/consent/con-u-demo-1-identity/correct", json={"field": "name", "new_value": "Somebody Else"}, headers=c)
    client.post("/messages/check", json={"text": "Pay fee http://x", "sender": "SAHARA-INFO", "area": "Elsewhere"}, headers=c)
    client.post("/cases/case-0001/decide", json={"action": "approve", "reason": "paid in the mess"}, headers=auth(client, "officer"))
    client.post("/rules/rule-stipend-short-payment/versions", json={"auto_handle_min": 0.95, "ask_more_min": 0.7, "red_flags": ["short_payment"]}, headers=auth(client, "admin"))
    client.post("/admin/demo/chaos", json={"identity_down": True}, headers=auth(client, "admin"))
    client.post("/apikeys", json={"name": "keep me", "scopes": ["cases:read"]}, headers=auth(client, "admin"))


def counts(db):
    return {m.__tablename__: db.query(m).count() for m in (Case, Claim, Decision, Job, Document, DocumentBlob, CheckedMessage, Consent, ConsentEvent)}


def test_only_admins_can_reset(client, demo):
    for who in ("citizen", "helper", "officer", "auditor"):
        assert reset(client, who).status_code == 403
    assert client.post("/admin/demo/reset", json={}).status_code == 401


def test_reset_restores_the_known_state_and_keeps_rules_and_audit(client, demo, db):
    baseline = counts(db)
    make_a_mess(client, db)
    assert counts(db) != baseline and db.get(User, "u-demo-1").name == "Somebody Else"
    audit_before = db.query(AuditLog).count()
    r = reset(client)
    assert r.status_code == 200
    body = r.json()
    assert body["reset"] is True and body["include_rules"] is False and body["deleted"]["cases"] > 0 and body["seeded"]["scam_checks"] == 60
    db.expire_all()
    assert counts(db) == baseline                                                 # exactly the seeded state again
    assert db.get(User, "u-demo-1").name == "Rukhsana Bibi"                       # the correction is undone
    assert db.get(Consent, "con-u-demo-1-identity").status == "granted" and db.get(Consent, "con-u-demo-5-payments").status == "withdrawn"
    assert db.query(CheckedMessage).count() == 60 and db.query(CheckedMessage).filter(CheckedMessage.area == "Elsewhere").count() == 0
    assert db.query(Job).count() == 0 and db.query(Document).count() == 0 and db.query(DocumentBlob).count() == 0
    # rules + history untouched, API keys untouched, outages and payments cleared
    assert [v.version for v in db.execute(select(RuleVersion).order_by(RuleVersion.version)).scalars()] == [1, 2]
    assert db.get(Rule, "rule-stipend-short-payment").active_version == 2 and db.query(ApiKey).count() == 1
    assert not any(CHAOS.values()) and PAYMENTS == {}
    # the audit log only grew; the reset itself is on record
    assert db.query(AuditLog).count() > audit_before
    row = db.execute(select(AuditLog).where(AuditLog.action == "demo.reset")).scalar_one()
    assert row.actor_id == "u-admin-1" and row.after["deleted"]["cases"] > 0 and row.after["include_rules"] is False and row.request_id
    assert db.query(AuditLog).filter(AuditLog.action == "auth.login").count() > 0  # earlier history survived


def test_include_rules_restores_rule_v1_and_drops_the_history(client, demo, db):
    make_a_mess(client, db)
    body = reset(client, include_rules=True).json()
    db.expire_all()
    assert body["include_rules"] is True and body["deleted"]["rule_versions"] == 2
    assert [v.version for v in db.query(RuleVersion)] == [1] and db.get(Rule, "rule-stipend-short-payment").active_version == 1
    assert db.execute(select(func.count()).select_from(Decision).where(Decision.rule_version == 1)).scalar_one() == db.query(Decision).count() == 5
    assert db.execute(select(AuditLog).where(AuditLog.action == "demo.reset")).scalar_one().after["include_rules"] is True


def test_reset_is_idempotent_and_each_call_is_audited(client, demo, db):
    reset(client)
    first = counts(db)
    reset(client)
    reset(client, include_rules=True)
    assert counts(db) == first
    assert db.query(AuditLog).filter(AuditLog.action == "demo.reset").count() == 3


def test_demo_mode_off_disables_reset_and_chaos(client, demo, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    r = reset(client)
    assert r.status_code == 403 and "DEMO_MODE=0" in r.json()["message"]
    assert client.post("/admin/demo/chaos", json={"identity_down": True}, headers=auth(client, "admin")).status_code == 403
    assert client.get("/admin/demo/chaos", headers=auth(client, "admin")).status_code == 403


def test_chaos_endpoint_roles_and_audit(client, demo, db):
    assert client.post("/admin/demo/chaos", json={"identity_down": True}, headers=auth(client, "officer")).status_code == 403
    r = client.post("/admin/demo/chaos", json={"identity_down": True, "ledger_down": True}, headers=auth(client, "admin")).json()
    assert r["identity_down"] and r["ledger_down"] and not r["payments_down"] and r["mocks"]["mode"] == "fake"
    a = db.execute(select(AuditLog).where(AuditLog.action == "demo.chaos")).scalar_one()
    assert a.before["identity_down"] is False and a.after["identity_down"] is True


def test_reset_script_main(SessionLocal, demo, monkeypatch, capsys):
    from app import db as db_module

    monkeypatch.setattr("sys.argv", ["app.demo", "reset", "--rules"])
    demo_mod.main()
    out = capsys.readouterr().out
    assert "'reset': True" in out and "'include_rules': True" in out
    assert db_module.session_factory() is SessionLocal
