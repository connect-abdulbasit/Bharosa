"""The 6 named demo scenarios reach different outcomes with the STUB AI (they run on the in-process fake mocks)."""
from sqlalchemy import select

from app import demo as demo_mod
from app import seed
from app.fake_mocks_client import PAYMENTS
from app.models import AuditLog, Case, CheckedMessage, Family, User
from tests.conftest import auth

SAY = {"transcript": "mujhe is mahine ke paisay nahi mile"}
SHORT = {"transcript": "mujhe paisay kam mile hain"}


def claim(client, who, body=SAY):
    r = client.post("/claims", json=body, headers=auth(client, who))
    assert r.status_code == 202, r.text
    return r.json()


def steps(b):
    return {s["step"]: s for s in b["pipeline_steps"]}


def officer_decide(client, case, action="approve", reason="Checked the evidence"):
    return client.post("/cases/%s/decide" % case, json={"action": action, "reason": reason}, headers=auth(client, "officer"))


def test_seed_adds_the_demo_layer_once(SessionLocal, demo):
    with SessionLocal() as db:
        assert db.query(CheckedMessage).count() == 60 and demo_mod.SCAM_CHECKS_TOTAL == 60
        names = {u.username: u.name for u in db.query(User).filter(User.username.like("s_-%"))}
        assert sorted(names) == ["s1-clean", "s2-spelling", "s3-shortpay", "s4-duplicate", "s5-consent", "s6-idown", "s7-autohandle"]
        assert db.query(Family).count() == 17 and db.query(User).count() == 22
        assert db.get(Case, "case-demo-4").status == "needs_more_proof"
        assert all(u.cnic.startswith("00000") and len(u.cnic) == 13 for u in db.query(User).filter(User.username.like("s_-%")))
        seed.run(db, scenarios=True)  # idempotent: nothing is duplicated
        assert db.query(CheckedMessage).count() == 60 and db.query(User).count() == 22 and db.query(Family).count() == 17


def test_scenario_1_clean_approval_pays_once(client, demo):
    b = claim(client, "s1-clean")
    assert b["status"] == "needs_more_proof" and b["decision"]["action"] == "ask_more" and b["finished"] is True
    assert [s["status"] for s in b["pipeline_steps"]] == ["done"] * 8 and "record found: Rukhsana Bibi" in steps(b)["identity_lookup"]["detail"]
    assert "short_payment" not in b["decision"]["trace"]["flags"] and b["decision"]["trace"]["shortfall"] == 12000
    ok = officer_decide(client, b["case_id"])
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    pay = ok.json()["decision"]["trace"]["payment"]
    assert pay["amount_pkr"] == 12000 and pay["payment_ref"].startswith("PAY-FAKE-") and pay["via"] == "payments"
    assert officer_decide(client, b["case_id"]).status_code == 409  # approving twice never pays twice
    assert len(PAYMENTS) == 1


def test_scenario_2_misspelled_name_asks_for_more(client, demo):
    b = claim(client, "s2-spelling")
    assert b["status"] == "needs_more_proof" and b["decision"]["action"] == "ask_more" and b["draft"]["claimant_name"] == "Mohammad Aslam"
    assert "name matched" in steps(b)["match_person"]["detail"] and "record found: Muhammad Aslam" in steps(b)["identity_lookup"]["detail"]
    assert b["decision"]["trace"]["flags"] == [] and b["decision"]["trace"]["needs"]


def test_scenario_3_short_payment_by_a_bad_agent_goes_to_an_officer(client, demo):
    b = claim(client, "s3-shortpay", SHORT)
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human"
    assert b["decision"]["trace"]["flags"] == ["short_payment"] and b["decision"]["trace"]["shortfall"] == 4000
    assert any("received PKR 8000 of 12000, paid by agent-099" in r for r in b["decision"]["reasons"])
    queue = client.get("/queue", headers=auth(client, "officer")).json()["items"]
    mine = [q for q in queue if q["case_id"] == b["case_id"]][0]
    assert mine["recommended_action"] == "send_to_human" and "Red flags" in mine["ai_reason"]
    pay = officer_decide(client, b["case_id"], reason="Agent short-paid her; topping up").json()["decision"]["trace"]["payment"]
    assert pay["amount_pkr"] == 4000


def test_scenario_4_duplicate_claim_goes_to_an_officer(client, demo, db):
    b = claim(client, "s4-duplicate")
    assert b["status"] == "with_officer" and b["decision"]["action"] == "send_to_human"
    assert any("Duplicate claim" in r and "case-demo-4" in r for r in b["decision"]["reasons"]) and "duplicate_claim" in b["decision"]["trace"]["flags"]
    assert b["pipeline_steps"][0]["status"] == "stopped" and db.get(Case, "case-demo-4").status == "needs_more_proof"


def test_scenario_5_withdrawn_consent_blocks_and_is_logged_then_resume(client, demo, db):
    b = claim(client, "s5-consent")
    assert b["status"] == "with_officer" and steps(b)["identity_lookup"]["status"] == "done"
    assert steps(b)["ledger_lookup"]["status"] == "failed" and "payments" in steps(b)["ledger_lookup"]["detail"]
    blocked = db.execute(select(AuditLog).where(AuditLog.action == "consent.blocked")).scalars().all()
    assert len(blocked) == 1 and blocked[0].actor_id == "u-demo-5" and blocked[0].after["scope"] == "payments"
    h = auth(client, "s5-consent")
    assert client.post("/consent", json={"scope": "payments"}, headers=h).json()["granted"] is True
    again = client.post("/claims/%s/resume" % b["claim_id"], headers=h).json()
    assert again["status"] == "needs_more_proof" and [s["status"] for s in again["pipeline_steps"]] == ["done"] * 8


def test_scenario_6_identity_service_down_pauses_then_resume_completes(client, demo):
    admin = auth(client, "admin")
    assert client.post("/admin/demo/chaos", json={"identity_down": True}, headers=admin).json()["identity_down"] is True
    b = claim(client, "s6-idown")
    assert b["status"] == "with_officer" and b["finished"] is False
    assert steps(b)["identity_lookup"]["status"] == "failed" and "simulated outage" in steps(b)["identity_lookup"]["detail"]
    notes = client.get("/cases/%s" % b["case_id"], headers=auth(client, "officer")).json()["notes"]
    assert any("Identity lookup failed" in n["text"] for n in notes)
    client.post("/admin/demo/chaos", json={"identity_down": False}, headers=admin)
    again = client.post("/claims/%s/resume" % b["claim_id"], headers=auth(client, "s6-idown")).json()
    assert again["status"] == "needs_more_proof" and again["finished"] is True and [s["status"] for s in again["pipeline_steps"]] == ["done"] * 8


def test_the_outcomes_are_all_different(client, demo):
    got = {}
    for who, body in (("s1-clean", SAY), ("s2-spelling", SAY), ("s3-shortpay", SHORT), ("s4-duplicate", SAY), ("s5-consent", SAY)):
        b = claim(client, who, body)
        got[who] = (b["status"], b["decision"]["action"], tuple(sorted(s["status"] for s in b["pipeline_steps"] if s["status"] != "done")))
    assert got["s1-clean"][0] == got["s2-spelling"][0] == "needs_more_proof"
    assert len({got["s3-shortpay"], got["s4-duplicate"], got["s5-consent"], got["s1-clean"]}) == 4


def test_helper_files_for_a_scenario_citizen(client, demo):
    r = client.post("/claims", json=dict(SAY, on_behalf_of="u-demo-1"), headers=auth(client, "helper"))
    assert r.status_code == 202 and r.json()["status"] == "needs_more_proof"
    fams = client.get("/helper/families", headers=auth(client, "helper")).json()["items"]
    assert len(fams) == 17 and {"Rukhsana Bibi", "Hameeda Begum"} <= {f["head_name"] for f in fams}


def test_scenario_7_auto_handled_payment_check_closes_with_no_payment(client, demo):
    """The one scenario where the AI itself says auto_handle: a structured question the official ledger answers with certainty."""
    h = auth(client, "s7-autohandle")
    r = client.post("/claims", json={"intent": "payment_check", "month": "2026-10"}, headers=h)
    assert r.status_code == 202
    b = client.get("/claims/%s" % r.json()["claim_id"], headers=h).json()
    d = b["decision"]
    assert b["status"] == "closed" and d["action"] == "auto_handle" and d["decided_by"] == "ai" and d["confidence"] >= 0.9
    assert [s["status"] for s in b["pipeline_steps"]] == ["done"] * 8 and d["rule_version"] == 1
    assert d["trace"]["payment_needed"] is False and d["trace"]["flags"] == [] and d["trace"]["intent"] == "payment_check"
    assert "PKR 12000" in b["explanation_en"] and "2026-10-05" in b["explanation_en"] and "agent-017" in b["explanation_en"] and "Nothing more is owed" in b["explanation_en"]
    assert "12000" in b["explanation_ur"] and "2026-10-05" in b["explanation_ur"]
    assert any("Nothing is owed" in x for x in d["reasons"])
    assert len(PAYMENTS) == 0  # no money moved, no officer involved
    case = client.get("/cases/%s" % b["case_id"], headers=auth(client, "officer")).json()
    assert case["status"] == "closed" and case["amount_claimed_pkr"] == 0 and any("answered automatically" in n["text"] for n in case["notes"])


def test_every_scenario_in_the_shared_file_behaves_as_documented(client, demo, db):
    """Data-driven: demo_people.json says what each request should give; the backend must agree (so the file stays honest)."""
    from app.demo_data import SCENARIOS

    admin = auth(client, "admin")
    for s in SCENARIOS:
        if s.get("setup", {}).get("chaos"):
            client.post("/admin/demo/chaos", json=s["setup"]["chaos"], headers=admin)
        r = client.post("/claims", json=s["request"], headers=auth(client, s["username"]))
        assert r.status_code == 202, s["key"]
        b = r.json()
        assert (b["status"], b["decision"]["action"]) == (s["expected_status"], s["expected_action"]), (s["key"], b["status"], b["decision"]["action"])
        if s.get("setup", {}).get("chaos"):
            client.post("/admin/demo/chaos", json={k: False for k in s["setup"]["chaos"]}, headers=admin)
