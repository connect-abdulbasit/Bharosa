"""'Did my payment arrive?': a structured question (no speech, nothing claimed), answered from the official ledger.
Only a CONFIRMED full payment may be auto-handled; everything else is routed to a person or back to the citizen."""
import pytest
from sqlalchemy import select

from app.models import AuditLog, Case, Claim
from app.models.base import utcnow
from tests.conftest import auth

PAID = {"payment_id": "p1", "amount_pkr": 12000, "date": "2026-10-05", "agent_id": "agent-017", "programme": "Sahara Relief Programme"}
CHECK = {"intent": "payment_check", "month": "2026-10"}


@pytest.fixture()
def named(mocks):
    """Identity record = the account's own name (citizen05 is 'Mohammad Rafiq'): a payment check matches on the ACCOUNT name."""
    mocks.identity_rec = {"full_name": "Mohammad Rafiq", "aliases": []}
    return mocks


def check(client, who="citizen05", **body):
    r = client.post("/claims", json=dict(CHECK, **body), headers=auth(client, who))
    assert r.status_code == 202, r.text
    return r.json()


def test_full_payment_is_auto_handled_and_closed_without_a_payment(client, named, db):
    named.payments = [PAID]
    b = check(client)
    d = b["decision"]
    assert b["status"] == "closed" and d["action"] == "auto_handle" and d["decided_by"] == "ai" and b["finished"] is True
    assert d["trace"]["flags"] == [] and d["trace"]["payment_needed"] is False and d["rule_version"] == 1
    assert "PKR 12000" in b["explanation_en"] and b["explanation_ur"]
    assert named.calls == ["identity", "ledger", "notify"] and named.disburse_keys == []     # no payment call, ever
    assert b["draft"]["claim_type"] == "payment_check" and b["draft"]["confidence"] == 1.0 and b["draft"]["model_version"] == "structured-input"
    actions = [r.action for r in db.execute(select(AuditLog).where(AuditLog.entity_id == b["case_id"])).scalars()]
    assert "agent.extract_claim" in actions and "ai.extract_claim" not in actions       # the AI reader was never used: nothing to read
    assert "ai.decide" in actions and "ai.match_person" in actions and "case.status_changed" not in actions


def test_nothing_on_record_asks_the_citizen_instead_of_claiming_all_is_well(client, named):
    b = check(client)  # empty ledger
    assert b["status"] == "needs_more_proof" and b["decision"]["action"] == "ask_more" and b["decision"]["decided_by"] == "agent"
    assert "override" in b["decision"]["trace"] and "No payment is on record" in b["decision"]["trace"]["needs"][0]
    assert "file a claim" in b["explanation_en"] and named.disburse_keys == []


def test_a_short_payment_goes_to_an_officer(client, named):
    named.payments = [dict(PAID, amount_pkr=8000, agent_id="agent-099")]
    b = check(client)
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human" and "short_payment" in b["decision"]["trace"]["flags"]
    assert any("paid by agent-099" in r for r in b["decision"]["reasons"]) and "not the full amount" in b["explanation_en"]
    assert named.disburse_keys == []  # asking never pays; only an officer's approval would


def test_the_short_payment_can_then_be_approved_once_by_an_officer(client, named):
    named.payments = [dict(PAID, amount_pkr=8000)]
    b = check(client)
    off = auth(client, "officer")
    r = client.post("/cases/%s/decide" % b["case_id"], json={"action": "approve", "reason": "Paid 8000, topping up 4000"}, headers=off)
    assert r.status_code == 200 and r.json()["decision"]["trace"]["payment"]["amount_pkr"] == 4000
    assert client.post("/cases/%s/decide" % b["case_id"], json={"action": "approve", "reason": "again"}, headers=off).status_code == 409
    assert len(named.disbursed) == 1


def test_a_duplicate_payment_in_the_ledger_goes_to_an_officer(client, named):
    named.payments = [PAID, dict(PAID, payment_id="p1-dup")]
    b = check(client)
    assert b["status"] == "with_officer" and "duplicate_payment" in b["decision"]["trace"]["flags_found"]


def test_a_check_never_blocks_or_is_blocked_by_a_real_claim(client, named):
    named.payments = [PAID]
    first = check(client)
    claim = client.post("/claims", json={"transcript": "mujhe is mahine ke paisay nahi mile"}, headers=auth(client, "citizen05")).json()
    assert first["status"] == "closed" and "duplicate_claim" not in claim["decision"]["trace"]["flags"]
    again = check(client)  # asking twice is fine
    assert again["status"] in ("closed", "with_officer", "needs_more_proof") and again["decision"]["trace"]["intent"] == "payment_check"
    assert "duplicate_claim" not in again["decision"]["trace"]["flags"]


def test_it_still_obeys_consent_and_the_live_rule(client, named):
    named.payments = [PAID]
    client.post("/consent/con-u-citizen-5-payments/withdraw", headers=auth(client, "citizen05"))
    blocked = check(client)
    assert blocked["status"] == "with_officer" and [s for s in blocked["pipeline_steps"] if s["status"] == "failed"][0]["step"] == "ledger_lookup"
    client.post("/consent", json={"scope": "payments"}, headers=auth(client, "citizen05"))
    # a stricter published rule means the same question is no longer auto-handled (thresholds come from the rule)
    client.post("/rules/rule-stipend-short-payment/versions", json={"auto_handle_min": 0.99, "ask_more_min": 0.6}, headers=auth(client, "admin"))
    named.identity_rec = {"full_name": "Shaista Parveen", "aliases": []}  # citizen06's own name
    strict = check(client, who="citizen06")
    assert strict["decision"]["rule_version"] == 2 and strict["decision"]["action"] != "auto_handle" and strict["status"] == "needs_more_proof"


def test_wrong_person_is_not_told_anything_good(client, mocks):
    mocks.payments = [PAID]
    mocks.identity_rec = {"full_name": "Somebody Else Entirely", "aliases": []}  # the record for this CNIC is not the account holder
    b = check(client)
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human"


def test_month_defaults_to_this_month_and_is_validated(client, named):
    b = client.post("/claims", json={"intent": "payment_check"}, headers=auth(client, "citizen05")).json()
    assert b["draft"]["period"] == utcnow().strftime("%Y-%m")
    for bad in ("2026-13", "October", "2026-1", "26-10"):
        r = client.post("/claims", json={"intent": "payment_check", "month": bad}, headers=auth(client, "citizen05"))
        assert r.status_code == 422 and "month" in r.json()["message"], bad
    assert client.post("/claims", json={"intent": "everything"}, headers=auth(client, "citizen05")).status_code == 422


def test_transcript_and_document_are_ignored_for_a_check(client, named, db):
    named.payments = [PAID]
    b = check(client, transcript="mujhe paisay kam mile hain")  # speech is not used: it is a question
    claim = db.get(Claim, b["claim_id"])
    assert claim.transcript is None and claim.claim_type == "payment_check" and claim.month == "2026-10" and b["status"] == "closed"


def test_a_helper_may_ask_for_a_linked_citizen_but_only_that_one(client, named):
    named.payments = [PAID]
    h = auth(client, "helper")
    assert client.post("/claims", json=dict(CHECK), headers=h).status_code == 422                                   # must name the citizen
    assert client.post("/claims", json=dict(CHECK, on_behalf_of="u-citizen-11"), headers=h).status_code == 403     # not linked
    ok = client.post("/claims", json=dict(CHECK, on_behalf_of="u-citizen-5"), headers=h)
    assert ok.status_code == 202 and ok.json()["status"] == "closed"


def test_closed_checks_are_listed_but_do_not_clutter_the_officer_queue(client, named, db):
    named.payments = [PAID]
    b = check(client)
    assert client.get("/cases/%s" % b["case_id"], headers=auth(client, "citizen05")).json()["status"] == "closed"
    queue_ids = [i["case_id"] for i in client.get("/queue", headers=auth(client, "officer")).json()["items"]]
    assert b["case_id"] not in queue_ids and db.get(Case, b["case_id"]).status == "closed"


def test_resume_of_a_finished_check_is_a_no_op(client, named):
    named.payments = [PAID]
    b = check(client)
    r = client.post("/claims/%s/resume" % b["claim_id"], headers=auth(client, "citizen05"))
    assert r.status_code == 202 and r.json()["status"] == "closed" and r.json()["finished"] is True
