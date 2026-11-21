"""The claim agent: happy path, bad data, failures, consent, duplicates, rule versions, resume."""
import pytest
from sqlalchemy import select

import bharosa_ai
from app.models import AuditLog, Decision
from app.services import pipeline
from contracts.ai_interface import ClaimDraft
from tests.conftest import auth

SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}  # stub AI reads this as a 'missing' claim for 2026-10


def claim(client, who="citizen05", **body):
    return client.post("/claims", json=dict(SPEECH, **body), headers=auth(client, who))


def decisions(db, case_id):
    return db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at)).scalars().all()


def audit_actions(db, case_id):
    return [r.action for r in db.execute(select(AuditLog).where(AuditLog.entity_id == case_id).order_by(AuditLog.id)).scalars()]


def test_happy_path_reaches_a_decision_with_rule_version(client, db, mocks):
    r = claim(client)
    assert r.status_code == 202
    b = r.json()
    # stub AI: claim confidence 0.81 -> between 0.60 and 0.90 -> ask_more -> needs_more_proof
    assert b["status"] == "needs_more_proof" and b["decision"]["action"] == "ask_more"
    assert b["decision"]["rule_version"] == 1 and b["draft"]["claim_type"] == "missing"
    assert b["explanation_en"] and b["explanation_ur"]
    assert [s["status"] for s in b["pipeline_steps"]] == ["done"] * 8
    row = decisions(db, b["case_id"])[-1]
    assert row.rule_id == "rule-stipend-short-payment" and row.rule_version == 1 and row.decided_by == "ai" and row.model_version
    assert mocks.calls == ["identity", "ledger", "notify"]  # consent was granted, so the citizen is notified too
    actions = audit_actions(db, b["case_id"])
    for a in ("ai.extract_claim", "agent.identity_lookup", "agent.ledger_lookup", "ai.match_person", "ai.decide", "ai.explain", "agent.notify"):
        assert a in actions, a
    ai_rows = db.execute(select(AuditLog).where(AuditLog.entity_id == b["case_id"], AuditLog.actor_type == "ai")).scalars().all()
    assert ai_rows and all(r.after["model_version"] and r.after["confidence"] is not None and "input" in r.after for r in ai_rows)
    detail = client.get("/cases/" + b["case_id"], headers=auth(client, "citizen05")).json()
    assert detail["rule_version"] == 1 and len(detail["pipeline_steps"]) == 8


def test_auto_handle_with_a_payment_still_needs_an_officer(client, db, mocks, monkeypatch):
    monkeypatch.setattr(bharosa_ai, "extract_claim", lambda t: ClaimDraft(
        claimant_name="Mohammad Aslam", claim_type="missing", amount_claimed_pkr=12000, period="2026-10", confidence=0.97, model_version="t"))
    b = claim(client).json()
    assert b["decision"]["action"] == "auto_handle"
    assert b["status"] == "with_officer"  # NOT approved: a payment is involved
    assert any("payment" in r.lower() for r in b["decision"]["reasons"])


@pytest.mark.parametrize("action,payment,needs,expected", [
    ("auto_handle", False, [], "approved"),
    ("auto_handle", True, [], "with_officer"),
    ("auto_handle", False, ["retake photo"], "needs_more_proof"),
    ("ask_more", False, [], "needs_more_proof"),
    ("send_to_human", False, [], "with_officer"),
])
def test_decision_mapping(action, payment, needs, expected):
    assert pipeline.map_decision(action, payment, needs)["status"] == expected


def test_misspelled_name_needs_more_proof(client, db, mocks):
    mocks.identity_rec = {"full_name": "Muhammad Aslam", "aliases": []}  # AI heard 'Mohammad Aslam'
    b = claim(client).json()
    assert b["status"] == "needs_more_proof"
    row = db.execute(select(AuditLog).where(AuditLog.entity_id == b["case_id"], AuditLog.action == "ai.match_person")).scalar_one()
    assert row.after["output"]["matched"] is True and row.after["output"]["score"] >= 0.9 and row.after["output"]["variants"]


def test_wrong_person_goes_to_a_human(client, mocks):
    mocks.identity_rec = {"full_name": "Zubaida Khatoon", "aliases": []}
    b = claim(client).json()
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human"


def test_identity_timeout_goes_to_officer_with_a_note_and_no_500(client, db, mocks):
    mocks.fail = {"identity"}
    r = claim(client)
    assert r.status_code == 202
    b = r.json()
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human" and b["decision"]["decided_by"] == "agent"
    assert b["decision"]["rule_version"] == 1
    failed = [s for s in b["pipeline_steps"] if s["status"] == "failed"]
    assert failed[0]["step"] == "identity_lookup" and "Identity lookup failed" in failed[0]["detail"]
    notes = client.get("/cases/" + b["case_id"], headers=auth(client, "officer")).json()["notes"]
    assert any("identity_lookup" in n["text"] and "Identity lookup failed" in n["text"] for n in notes)
    assert "ledger" not in mocks.calls  # nothing after the failed step ran


def test_resume_continues_without_redoing_finished_steps(client, db, mocks):
    mocks.fail = {"identity"}
    first = claim(client).json()
    mocks.fail = set()
    again = client.post("/claims/%s/resume" % first["claim_id"], headers=auth(client, "citizen05")).json()
    assert [s["status"] for s in again["pipeline_steps"]] == ["done"] * 8 and again["status"] == "needs_more_proof"
    assert audit_actions(db, first["case_id"]).count("ai.extract_claim") == 1  # NOT run twice
    # resuming a finished claim is a harmless no-op
    n = len(audit_actions(db, first["case_id"]))
    same = client.post("/claims/%s/resume" % first["claim_id"], headers=auth(client, "citizen05")).json()
    assert same["status"] == again["status"] and len(audit_actions(db, first["case_id"])) == n


def test_resume_is_limited_to_people_who_can_see_the_claim(client, mocks):
    cid = claim(client).json()["claim_id"]
    assert client.post("/claims/%s/resume" % cid, headers=auth(client, "citizen")).status_code == 404
    assert client.post("/claims/%s/resume" % cid, headers=auth(client, "officer")).status_code == 403
    assert client.post("/claims/%s/resume" % cid, headers=auth(client, "helper")).status_code == 202  # linked


def test_withdrawn_payments_consent_blocks_the_ledger_step_and_logs_it(client, db, mocks):
    pay = "con-u-citizen-5-payments"
    assert client.post("/consent/%s/withdraw" % pay, json={"reason": "no"}, headers=auth(client, "citizen05")).status_code == 200
    b = claim(client).json()
    assert b["status"] == "with_officer"
    assert "identity" in mocks.calls and "ledger" not in mocks.calls
    blocked = db.execute(select(AuditLog).where(AuditLog.action == "consent.blocked")).scalars().all()
    assert len(blocked) == 1 and blocked[0].after["scope"] == "payments" and blocked[0].actor_id == "u-citizen-5"
    notes = client.get("/cases/" + b["case_id"], headers=auth(client, "officer")).json()["notes"]
    assert any("payments" in n["text"] for n in notes)


def test_rule_change_new_claim_uses_v2_old_decision_keeps_v1(client, db, mocks):
    old = claim(client, "citizen05").json()
    admin = auth(client, "admin")
    r = client.post("/rules/rule-stipend-short-payment/versions", headers=admin,
                    json={"auto_handle_min": 0.95, "ask_more_min": 0.7, "red_flags": ["short_payment"], "note": "stricter"})
    assert r.status_code == 200 and r.json()["version"] == 2
    new = claim(client, "citizen06").json()  # no publish/restart in between
    assert new["decision"]["rule_version"] == 2
    off = auth(client, "officer")
    assert client.get("/cases/" + old["case_id"], headers=off).json()["decision"]["rule_version"] == 1
    assert client.get("/cases/" + new["case_id"], headers=off).json()["decision"]["rule_version"] == 2
    rows = [decisions(db, old["case_id"])[-1], decisions(db, new["case_id"])[-1]]
    assert {(r.rule_id, r.rule_version) for r in rows} == {("rule-stipend-short-payment", 1), ("rule-stipend-short-payment", 2)}


def test_duplicate_claim_for_the_same_month_goes_to_officer(client, db, mocks):
    first = claim(client).json()
    second = claim(client).json()
    assert second["case_id"] != first["case_id"]
    assert second["status"] == "with_officer" and second["decision"]["action"] == "send_to_human"
    assert any("Duplicate" in r and first["case_id"] in r for r in second["decision"]["reasons"])
    assert "duplicate_claim" in second["decision"]["trace"]["flags"]
    assert second["pipeline_steps"][0] == {"step": "extract_claim", "status": "stopped", "detail": second["decision"]["reasons"][0]}
    assert mocks.calls.count("identity") == 1  # the duplicate stopped before any new lookup
    assert client.get("/cases/" + first["case_id"], headers=auth(client, "officer")).json()["status"] == "needs_more_proof"


def test_rejected_claim_does_not_block_a_new_one(client, mocks):
    first = claim(client).json()
    off = auth(client, "officer")
    assert client.post("/cases/%s/decide" % first["case_id"], json={"action": "reject", "reason": "wrong person"}, headers=off).status_code == 200
    assert claim(client).json()["status"] == "needs_more_proof"


def test_short_payment_is_a_red_flag_for_a_human(client, mocks):
    mocks.payments = [{"payment_id": "p1", "amount_pkr": 8000, "date": "2026-10-05", "agent_id": "a1", "programme": "Sahara Relief Programme"}]
    b = claim(client, transcript="mujhe paisay kam mile hain").json()
    assert b["status"] == "with_officer" and "short_payment" in b["decision"]["trace"]["flags"]
    assert b["decision"]["trace"]["shortfall"] == 4000


def test_duplicate_payment_in_ledger_is_flagged(client, mocks):
    p = {"payment_id": "p1", "amount_pkr": 12000, "date": "2026-10-05", "agent_id": "a1", "programme": "Sahara Relief Programme"}
    mocks.payments = [p, dict(p, payment_id="p1-dup")]
    b = claim(client).json()
    assert "duplicate_payment" in b["decision"]["trace"]["flags_found"] and b["status"] == "with_officer"


def test_unclear_speech_asks_to_repeat(client, mocks):
    b = claim(client, transcript="hi").json()
    assert b["status"] == "needs_more_proof" and "again" in b["explanation_en"].lower()
    assert mocks.calls == []  # nothing was looked up for a claim nobody understood


def test_unexpected_bug_never_becomes_a_500(client, db, mocks, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(bharosa_ai, "match_person", boom)
    r = claim(client)
    assert r.status_code == 202 and r.json()["status"] == "with_officer"
    failed = [s for s in r.json()["pipeline_steps"] if s["status"] == "failed"][0]
    assert failed["step"] == "match_person" and "internal error" in failed["detail"] and "exploded" not in r.text


def test_helper_must_name_a_linked_citizen(client, mocks):
    h = auth(client, "helper")
    assert client.post("/claims", json=SPEECH, headers=h).status_code == 422
    assert client.post("/claims", json=dict(SPEECH, on_behalf_of="u-citizen-11"), headers=h).status_code == 403
    ok = client.post("/claims", json=dict(SPEECH, on_behalf_of="u-citizen-5"), headers=h)
    assert ok.status_code == 202
    assert client.get("/cases/" + ok.json()["case_id"], headers=auth(client, "citizen05")).json()["citizen_name"] == "Mohammad Rafiq"


def test_cannot_look_up_someone_elses_id_number(client, mocks):
    r = claim(client, cnic="0000042101001")
    assert r.status_code == 422 and mocks.calls == []
