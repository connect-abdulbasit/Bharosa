"""The five scenarios from e2e/README.md plus chaos, RBAC and services checks. Public HTTP interfaces only."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from conftest import MOCKS, SERVICE_KEY, SERVICES
from services.webhooks.service import verify

S1_CNIC = "0000042101101"
PAY_CHECK = {"intent": "payment_check", "month": "2026-10"}


def step(claim, name):
    return {s["step"]: s for s in claim["pipeline_steps"]}[name]


def all_done(claim):
    return all(s["status"] == "done" for s in claim["pipeline_steps"])


# 1. Happy path: ask for proof, officer approves, paid exactly once through the REAL mocks ----------------------------
def test_1_happy_path_pays_once_after_officer_approval(api):
    c = api.claim("s1-clean")
    assert c["status"] == "needs_more_proof" and c["decision"]["action"] == "ask_more"
    assert isinstance(c["decision"]["rule_version"], int) and all_done(c)
    off, body = api.login("officer"), {"action": "approve", "reason": "Ledger confirms nothing was paid"}
    s, d = api("POST", "/cases/%s/decide" % c["case_id"], off, json=body)
    pay = d["decision"]["trace"]["payment"]
    assert s == 200 and d["status"] == "approved" and pay["amount_pkr"] == 12000 and pay["payment_ref"].startswith("PAY-")
    assert api("POST", "/cases/%s/decide" % c["case_id"], off, json=body)[0] == 409  # a double click never pays twice
    assert api.mocks_calls()["POST /payments/disburse"] == 1
    assert api.audit(action="payment.release", entity_id=c["case_id"])["total"] == 1
    assert api.audit(entity="case", entity_id=c["case_id"])["total"] >= 3  # every state change is on the log


# 2. Misspelled name: matched as a variant, lower confidence, never silently approved -------------------------------
def test_2_misspelled_name_is_never_auto_approved(api):
    c = api.claim("s2-spelling")
    assert "name matched" in step(c, "match_person")["detail"]
    assert c["status"] == "needs_more_proof" and c["decision"]["action"] != "auto_handle"


# 3. Identity service down (every failure style): calm hand-over to an officer, resumes when it is back ---------------
@pytest.mark.parametrize("switch", ["error_500", "timeout", "missing_record"])
def test_3_identity_failure_goes_to_an_officer_then_resumes(api, switch):
    assert api("POST", "/chaos", base=MOCKS, json={switch: True})[0] == 200
    tok = api.login("s6-idown")
    c = api.claim("s6-idown")  # claim() asserts 202: the citizen never sees a 500
    assert c["status"] == "with_officer" and step(c, "identity_lookup")["status"] == "failed"
    assert c["decision"]["action"] == "send_to_human"
    api("POST", "/chaos/reset", base=MOCKS)
    api("POST", "/claims/%s/resume" % c["claim_id"], tok)
    r = api.settle(tok, c["claim_id"])
    assert r["status"] == "needs_more_proof" and all_done(r)  # picked up from the failed step, not restarted


# 4. Consent withdrawn: the next claim makes NO ledger call, it is logged, and granting again resumes --------------
def test_3c_payment_record_down_pauses_at_the_ledger_not_at_identity(api):
    """Chaos Panel "payment record down" = the mocks' ledger-only switch: identity still works, the claim stops at ledger_lookup."""
    assert api("POST", "/admin/demo/chaos", api.login("admin"), json={"ledger_down": True})[0] == 200
    try:
        c = api.claim("demo-live")
        steps = {x["step"]: x["status"] for x in c["pipeline_steps"]}
        assert c["status"] == "with_officer" and steps["identity_lookup"] == "done" and steps["ledger_lookup"] == "failed"
    finally:
        api("POST", "/admin/demo/chaos", api.login("admin"), json={"ledger_down": False})
    assert api("GET", "/identity/0000042101108", base=MOCKS)[0] == 200 and api("GET", "/ledger/0000042101108", base=MOCKS)[0] == 200


def test_4_withdrawn_payments_consent_blocks_the_ledger_call(api):
    tok = api.login("s1-clean")
    consent = {c["scope"]: c for c in api("GET", "/consent", tok)[1]["items"]}["payments"]
    assert api("POST", "/consent/%s/withdraw" % consent["id"], tok, json={"reason": "e2e"})[0] == 200
    before = api.audit(action="consent.blocked", actor_id="u-demo-1")["total"]
    c = api.claim("s1-clean")
    assert c["status"] == "with_officer" and step(c, "ledger_lookup")["status"] == "failed"
    calls = api.mocks_calls()
    assert "GET /identity/" + S1_CNIC in calls                    # identity consent was still granted
    assert "GET /ledger/" + S1_CNIC not in calls                  # the proof: the mock was never asked
    assert api.audit(action="consent.blocked", actor_id="u-demo-1")["total"] == before + 1
    api("POST", "/consent", tok, json={"scope": "payments"})
    api("POST", "/claims/%s/resume" % c["claim_id"], tok)
    r = api.settle(tok, c["claim_id"])
    assert r["status"] == "needs_more_proof" and api.mocks_calls()["GET /ledger/" + S1_CNIC] == 1


# 5. Rule changed live: old decision keeps its version, the next one uses the new version -----------------------------
def test_5_rule_change_applies_live_and_old_decisions_keep_their_version(api):
    old = api.claim("s1-clean")
    assert old["decision"]["rule_version"] == 1
    adm = api.login("admin")
    rule_id = api("GET", "/rules", adm)[1]["items"][0]["id"]
    latest = max(api("GET", "/rules/%s/versions" % rule_id, adm)[1]["versions"], key=lambda v: v["version"])
    new = {k: latest[k] for k in ("red_flags", "logic", "ask_more_min")}
    s, v = api("POST", "/rules/%s/versions" % rule_id, adm, json=dict(new, auto_handle_min=0.95, note="e2e stricter"))
    assert s in (200, 201) and v["version"] == 2
    fresh = api.claim("s2-spelling")
    assert fresh["decision"]["rule_version"] == 2                                                  # live, no redeploy
    assert api("GET", "/claims/%s" % old["claim_id"], api.login("s1-clean"))[1]["decision"]["rule_version"] == 1


# 6. Duplicate payment (chaos): a normally auto-closed check must go to a human -----------------------------------
def test_6_duplicate_payment_is_flagged_not_closed(api):
    ok = api.claim("s7-autohandle", PAY_CHECK)
    assert ok["status"] == "closed" and ok["decision"]["action"] == "auto_handle"  # baseline: clean ledger auto-closes
    api("POST", "/reset", base=MOCKS)
    api("POST", "/admin/demo/reset", api.login("admin"), json={"include_rules": True})
    api("POST", "/chaos", base=MOCKS, json={"duplicate_payment": True})
    c = api.claim("s7-autohandle", PAY_CHECK)
    assert c["status"] == "with_officer" and c["decision"]["action"] == "send_to_human"
    assert "duplicate_payment" in c["decision"]["trace"]["flags"]


# 7. Security: server-side RBAC and calm errors ---------------------------------------------------------------------
def test_7_rbac_is_enforced_by_the_server(api):
    c = api.claim("s1-clean")
    decide = ("POST", "/cases/%s/decide" % c["case_id"])
    body = {"json": {"action": "approve", "reason": "x"}}
    assert api(*decide, api.login("s1-clean"), **body)[0] == 403         # citizen cannot approve
    assert api(*decide, api.login("auditor"), **body)[0] == 403          # auditor cannot write
    assert api(*decide, None, **body)[0] == 401                          # no token
    assert api(*decide, "tampered.token.value", **body)[0] == 401        # bad token
    assert api("GET", "/audit", api.login("s1-clean"))[0] == 403         # citizen cannot read the audit log
    assert api("GET", "/audit", api.login("auditor"))[0] == 200          # auditor can
    assert api("GET", "/cases/does-not-exist", api.login("s1-clean"))[0] == 404


# 8. Services: notifications obey consent, webhooks are signed and verifiable ---------------------------------------
HDR = {"X-Service-Key": SERVICE_KEY}


@pytest.mark.services
def test_8_notifications_follow_consent(api):
    s, n = api("POST", "/notifications/send", None, base=SERVICES, headers=HDR, json={"cnic": S1_CNIC, "to": "0300-0000000", "key": "case_approved"})
    assert n["status"] == "blocked"                                      # default deny
    api("POST", "/notifications/consent", None, base=SERVICES, headers=HDR, json={"cnic": S1_CNIC, "granted": True})
    assert api("POST", "/notifications/send", None, base=SERVICES, headers=HDR, json={"cnic": S1_CNIC, "to": "x", "key": "case_approved"})[1]["status"] in ("sent", "failed")
    api("POST", "/notifications/consent", None, base=SERVICES, headers=HDR, json={"cnic": S1_CNIC, "granted": False})
    assert api("POST", "/notifications/send", None, base=SERVICES, headers=HDR, json={"cnic": S1_CNIC, "to": "x", "key": "case_approved"})[1]["status"] == "blocked"
    assert api("GET", "/jobs", None, base=SERVICES)[0] == 401            # no service key


@pytest.mark.services
def test_9_webhook_is_signed_and_tamper_evident(api):
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append((self.headers.get("X-Bharosa-Signature", ""), self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    s, sub = api("POST", "/webhooks/subscriptions", None, base=SERVICES, headers=HDR,
                 json={"url": "http://127.0.0.1:%d/hook" % srv.server_port, "events": ["case.status_changed"]})
    assert s == 201, "services must run with WEBHOOKS_ALLOW_LOCAL=1 for local demos: %s" % sub
    api("POST", "/events", None, base=SERVICES, headers=HDR, json={"event": "case.status_changed", "payload": {"case_id": "case-e2e"}})
    for _ in range(50):
        if got:
            break
        time.sleep(0.1)
    srv.shutdown()
    api("DELETE", "/webhooks/subscriptions/" + sub["id"], None, base=SERVICES, headers=HDR)
    sig, body = got[0]
    assert verify(sub["secret"], sig, body) and json.loads(body)["simulated"] is True
    assert not verify(sub["secret"], sig, body.replace(b"case-e2e", b"case-xxx"))  # one changed byte breaks it


# 10. Digital Twin: a loosening rule is flagged BEFORE publishing, and previewing changes nothing ----------------------
def test_10_digital_twin_previews_without_publishing(api):
    from conftest import BASE
    from services.digital_twin.twin import Twin
    t = Twin(BASE)
    t.login("admin", "admin-demo-123")
    sims_before = api.audit(action="rule.simulate")["total"]  # the audit log is append-only: it survives resets, so compare
    assert t.seed_history() == 7
    loose = t.preview("admin", 0.80, 0.60)             # stub AI confidence is 0.81, so 0.80 would auto-handle ask_more cases
    assert loose["less_human_oversight"] >= 1 and loose["verdict"].startswith("REVIEW")
    tight = t.preview("admin", 0.95, 0.85)
    assert tight["more_human_oversight"] >= 1 and tight["less_human_oversight"] == 0 and tight["verdict"].startswith("TIGHTER")
    adm = api.login("admin")
    assert api("GET", "/rules", adm)[1]["items"][0]["current_version"] == 1      # nothing was published
    assert api.audit(action="rule.publish")["total"] == 0 and api.audit(action="rule.simulate")["total"] == sims_before + 2
