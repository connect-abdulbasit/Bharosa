"""POST /rules/{id}/simulate: re-run only the decide step of past decisions under a proposed rule. Read-only."""
import pytest
from sqlalchemy import select

import bharosa_ai
from app.models import (ApiKey, AuditLog, Case, CheckedMessage, Claim, Consent, ConsentEvent, Decision, Document, Job, Rule, RuleVersion,
                        User)
from app.models.base import utcnow
from contracts.ai_interface import ClaimDraft
from tests.conftest import auth

URL = "/rules/rule-stipend-short-payment/simulate"
SAY = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def sim(client, who="admin", **body):
    return client.post(URL, json=dict({"auto_handle_min": 0.9, "ask_more_min": 0.6}, **body), headers=auth(client, who))


def claim_with_confidence(client, who, conf, monkeypatch):
    monkeypatch.setattr(bharosa_ai, "extract_claim", lambda t: ClaimDraft(
        claimant_name="Mohammad Aslam", claim_type="missing", amount_claimed_pkr=12000, period="2026-10", confidence=conf, model_version="t"))
    r = client.post("/claims", json=SAY, headers=auth(client, who))
    assert r.status_code == 202
    return r.json()


@pytest.fixture()
def history(client, mocks, monkeypatch):
    """3 real pipeline decisions: auto_handle (conf .95), ask_more (.75), send_to_human (.5)."""
    return {"auto": claim_with_confidence(client, "citizen05", 0.97, monkeypatch), "ask": claim_with_confidence(client, "citizen06", 0.75, monkeypatch),
            "human": claim_with_confidence(client, "citizen07", 0.50, monkeypatch)}


def audit_count(db):
    return db.query(AuditLog).filter(AuditLog.action != "auth.login").count()  # logging in is audited too; ignore it here


def tables(db):
    return {m.__tablename__: db.query(m).count() for m in (Case, Claim, Decision, Job, Document, CheckedMessage, Consent, ConsentEvent, Rule, RuleVersion, User, ApiKey)}


def test_baseline_actions_are_what_we_expect(history):
    assert [history[k]["decision"]["action"] for k in ("auto", "ask", "human")] == ["auto_handle", "ask_more", "send_to_human"]


def test_stricter_rule_would_change_the_auto_handle(client, history):
    r = sim(client, auto_handle_min=0.99)
    assert r.status_code == 200
    b = r.json()
    assert b["rule_id"] == "rule-stipend-short-payment" and b["current_version"] == 1 and b["simulated"] is True
    assert b["total_cases"] == 3 + 4 and b["simulated_cases"] == 3 and b["skipped_no_inputs"] == 4  # 4 seeded samples have no stored inputs
    assert b["would_change"] == 1 and b["by_transition"] == {"auto_handle -> ask_more": 1}
    assert b["examples"] == [{"case_id": history["auto"]["case_id"], "old_action": "auto_handle", "new_action": "ask_more"}]
    assert b["proposed"]["auto_handle_min"] == 0.99


def test_looser_floor_moves_the_human_case(client, history):
    b = sim(client, ask_more_min=0.45).json()
    assert b["would_change"] == 1 and b["by_transition"] == {"send_to_human -> ask_more": 1}
    assert b["examples"][0]["case_id"] == history["human"]["case_id"]


def test_same_rule_changes_nothing(client, history):
    b = sim(client).json()
    assert b["would_change"] == 0 and b["by_transition"] == {} and b["examples"] == [] and b["simulated_cases"] == 3


def test_removing_a_red_flag_changes_flagged_cases(client, mocks, monkeypatch):
    mocks.payments = [{"payment_id": "p1", "amount_pkr": 8000, "date": "2026-10-05", "agent_id": "agent-099", "programme": "Sahara Relief Programme"}]
    b = client.post("/claims", json={"transcript": "mujhe paisay kam mile hain"}, headers=auth(client, "citizen05")).json()
    assert b["decision"]["action"] == "send_to_human" and b["decision"]["trace"]["flags"] == ["short_payment"]
    out = sim(client, red_flags=[]).json()  # same thresholds, but short payments are no longer a red flag
    assert out["by_transition"] == {"send_to_human -> ask_more": 1} and out["examples"][0]["case_id"] == b["case_id"]
    assert sim(client, red_flags=["short_payment"]).json()["would_change"] == 0


def test_it_is_read_only_apart_from_one_audit_row(client, db, history, monkeypatch):
    before, audits = tables(db), audit_count(db)
    versions = [(v.version, v.thresholds) for v in db.query(RuleVersion)]
    sim(client, auto_handle_min=0.99)
    sim(client, ask_more_min=0.45)
    db.expire_all()
    assert tables(db) == before and [(v.version, v.thresholds) for v in db.query(RuleVersion)] == versions
    assert db.get(Rule, "rule-stipend-short-payment").active_version == 1
    assert audit_count(db) == audits + 2  # exactly one audit row per simulation, nothing else
    rows = db.execute(select(AuditLog).where(AuditLog.action == "rule.simulate").order_by(AuditLog.id)).scalars().all()
    assert len(rows) == 2 and rows[0].actor_id == "u-admin-1" and rows[0].after["would_change"] == 1 and rows[0].after["auto_handle_min"] == 0.99
    # and a real claim afterwards still uses the REAL active rule (v1), proving nothing leaked into the live rule
    assert claim_with_confidence(client, "citizen08", 0.97, monkeypatch)["decision"]["rule_version"] == 1


def test_examples_are_capped_at_20(client, db):
    for i in range(25):
        cid = "case-sim-%02d" % i
        db.add(Case(id=cid, citizen_id="u-citizen-5", created_by="u-citizen-5", status="with_officer", risk_score=0.1, confidence=0.95, notes=[], created_at=utcnow(), updated_at=utcnow()))
        db.flush()
        db.add(Claim(case_id=cid, claim_type="missing", expected_amount=12000, received_amount=0, month="2026-10", data={"pipeline": {
            "outputs": {"extract_claim": {"draft": {"claimant_name": "Mohammad Aslam", "claim_type": "missing", "amount_claimed_pkr": 12000,
                                                    "period": "2026-10", "confidence": 0.97, "model_version": "t"}},
                        "match_person": {"match": {"match_id": "x", "score": 1.0, "confidence": 0.97, "variants": [], "model_version": "t"}},
                        "ledger_lookup": {"payments": []}}, "flags_found": [], "payment_needed": True}}))
        db.add(Decision(case_id=cid, action="auto_handle", confidence=0.97, reasons=[], trace={}, rule_id="rule-stipend-short-payment", rule_version=1,
                        model_version="t", decided_by="ai"))
    db.commit()
    b = sim(client, auto_handle_min=0.99).json()
    assert b["would_change"] == 25 and len(b["examples"]) == 20 and b["by_transition"] == {"auto_handle -> ask_more": 25}
    assert all(e["old_action"] == "auto_handle" and e["new_action"] == "ask_more" for e in b["examples"])


def test_only_the_latest_ai_decision_per_case_counts(client, db, history):
    first = db.execute(select(Decision).where(Decision.case_id == history["auto"]["case_id"])).scalars().first()
    older = Decision(case_id=first.case_id, action="send_to_human", confidence=0.2, reasons=[], trace={}, rule_id=first.rule_id, rule_version=1,
                     model_version="t", decided_by="ai", created_at=first.created_at.replace(year=2020))
    db.add(older)
    db.commit()
    assert sim(client, auto_handle_min=0.99).json()["total_cases"] == 7  # still 3 + 4 cases, not 8


def test_validation_and_permissions(client, history, db):
    audits = audit_count(db)
    unsafe = {"if": [True, "auto_handle", "auto_handle"]}
    r = sim(client, logic=unsafe)
    assert r.status_code == 422 and "Unsafe rule" in r.json()["message"]
    assert sim(client, auto_handle_min=0.5, ask_more_min=0.8).status_code == 422
    assert audit_count(db) == audits  # nothing written for a rejected proposal
    assert client.post("/rules/nope/simulate", json={"auto_handle_min": 0.9, "ask_more_min": 0.6}, headers=auth(client, "admin")).status_code == 404
    for who in ("citizen", "helper", "officer", "auditor"):
        assert sim(client, who).status_code == 403, who
    assert client.post(URL, json={}).status_code == 401


def test_omitted_red_flags_keep_the_current_flags_in_a_what_if(client, mocks):
    mocks.payments = [{"payment_id": "p1", "amount_pkr": 8000, "date": "2026-10-05", "agent_id": "agent-099", "programme": "Sahara Relief Programme"}]
    b = client.post("/claims", json={"transcript": "mujhe paisay kam mile hain"}, headers=auth(client, "citizen05")).json()
    assert b["decision"]["trace"]["flags"] == ["short_payment"]
    inherited = sim(client, auto_handle_min=0.99)  # red_flags NOT mentioned: the live rule's flags still apply
    assert inherited.json()["would_change"] == 0 and "short_payment" in inherited.json()["proposed"]["red_flags"]
    cleared = sim(client, red_flags=[])             # explicitly clearing them is a visible, deliberate choice
    assert cleared.json()["would_change"] == 1 and cleared.json()["proposed"]["red_flags"] == []
