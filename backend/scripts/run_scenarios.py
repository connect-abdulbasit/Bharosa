#!/usr/bin/env python3
"""Run the 7 demo scenarios over HTTP against a running backend and report each outcome. Stdlib only.

    python backend/scripts/run_scenarios.py [BASE_URL]        (default http://localhost:8000)

It first resets the demo state (POST /admin/demo/reset with include_rules=true), so it is safe to run repeatedly.
Works with the backend's BUILT-IN fake mocks (MOCKS_URL empty) and with the REAL mocks service (it serves the same
people, generated from contracts/fixtures/demo_people.json; set MOCKS_HOST_URL if it is not http://localhost:8001).
Exit code 0 = every scenario behaved as documented in docs/demo-scenarios.md.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
PASSWORD = "citizen-demo-123"  # FAKE demo passwords (see README)
SAY = {"transcript": "mujhe is mahine ke paisay nahi mile"}
SHORT = {"transcript": "mujhe paisay kam mile hain"}


MOCKS = {"url": None}  # set in main() when the backend uses the REAL mocks service


def outage(on):
    """Identity outage: the fake client's switch via the admin API, or the real mocks' own chaos switch (error_500)."""
    if MOCKS["url"]:
        req = urllib.request.Request(MOCKS["url"] + "/chaos", method="POST", data=json.dumps({"error_500": bool(on)}).encode(),
                                     headers={"content-type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    else:
        call("POST", "/admin/demo/chaos", {"identity_down": bool(on)}, _tokens["admin"])


def call(method, path, body=None, token=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else None)


_tokens = {}


def login(user, password=PASSWORD):
    """Tokens are cached; /auth/login is rate limited (5 per minute per IP), so when we hit it we wait for the window to reset."""
    if user in _tokens:
        return _tokens[user]
    for attempt in range(3):
        s, b = call("POST", "/auth/login", {"username": user, "password": password})
        if s == 200:
            _tokens[user] = b["access_token"]
            return _tokens[user]
        if s == 429:
            print("   (login rate limit: 5 per minute per IP: waiting 61 s for the window to reset)")
            time.sleep(61)
            continue
        raise SystemExit("login failed for %s: %s %s" % (user, s, b))
    raise SystemExit("login rate limited")


def settle(token, claim_id):
    """Poll the cheap progress endpoint until the background job is no longer queued/running, then return the full claim."""
    for _ in range(300):
        s, p = call("GET", "/claims/%s/progress" % claim_id, token=token)
        if not p["active"]:
            break
        time.sleep(0.1)
    return call("GET", "/claims/%s" % claim_id, token=token)[1]


def file_claim(token, body=SAY):
    s, b = call("POST", "/claims", body, token)
    assert s == 202, "POST /claims -> %s %s" % (s, b)
    return settle(token, b["claim_id"])


def steps(c):
    return {s["step"]: s for s in c["pipeline_steps"]}


def show(c):
    d = c["decision"]
    print("   status=%s  AI=%s (confidence %.2f, rule v%s)  steps done=%d/8" % (
        c["status"], d["action"], d["confidence"], d["rule_version"], sum(1 for s in c["pipeline_steps"] if s["status"] == "done")))
    for r in d["reasons"][:3]:
        print("   - " + r)


def s1(t):
    c = file_claim(login("s1-clean"))
    show(c)
    assert c["status"] == "needs_more_proof" and c["decision"]["action"] == "ask_more"
    off = login("officer", "officer-demo-123")
    s, d = call("POST", "/cases/%s/decide" % c["case_id"], {"action": "approve", "reason": "Clean claim, ledger confirms nothing was paid"}, off)
    pay = d["decision"]["trace"]["payment"]
    print("   officer approves -> %s, paid PKR %s, ref %s" % (d["status"], pay["amount_pkr"], pay["payment_ref"]))
    s2, e = call("POST", "/cases/%s/decide" % c["case_id"], {"action": "approve", "reason": "Clicked twice"}, off)
    print("   approving again -> HTTP %s (%s): nobody is paid twice" % (s2, e["error"]))
    assert d["status"] == "approved" and pay["amount_pkr"] == 12000 and s2 == 409
    return "needs_more_proof -> officer approves -> paid once (PKR 12000)"


def s2(t):
    c = file_claim(login("s2-spelling"))
    show(c)
    print("   identity: %s | match: %s" % (steps(c)["identity_lookup"]["detail"], steps(c)["match_person"]["detail"]))
    assert c["status"] == "needs_more_proof" and "name matched" in steps(c)["match_person"]["detail"]
    return "needs_more_proof (name matched only as a spelling variant)"


def s3(t):
    c = file_claim(login("s3-shortpay"), SHORT)
    show(c)
    assert c["status"] == "with_officer" and "short_payment" in c["decision"]["trace"]["flags"]
    assert any("agent-099" in r for r in c["decision"]["reasons"])
    return "with_officer: short payment of PKR 4000, paid by agent-099"


def s4(t):
    c = file_claim(login("s4-duplicate"))
    show(c)
    assert c["status"] == "with_officer" and "duplicate_claim" in c["decision"]["trace"]["flags"]
    return "with_officer: duplicate of open case case-demo-4"


def s5(t):
    tok = login("s5-consent")
    before = call("GET", "/audit?action=consent.blocked&actor_id=u-demo-5", token=t["admin"])[1]["total"]  # the audit log is never wiped
    c = file_claim(tok)
    show(c)
    print("   ledger_lookup: %s - %s" % (steps(c)["ledger_lookup"]["status"], steps(c)["ledger_lookup"]["detail"]))
    assert c["status"] == "with_officer" and steps(c)["ledger_lookup"]["status"] == "failed"
    s, a = call("GET", "/audit?action=consent.blocked&actor_id=u-demo-5", token=t["admin"])
    print("   audit: +%d 'consent.blocked' entry for this citizen (scope=%s, request_id %s)" % (a["total"] - before, a["items"][0]["after"]["scope"], a["items"][0]["request_id"][:8]))
    assert a["total"] == before + 1
    call("POST", "/consent", {"scope": "payments"}, tok)
    call("POST", "/claims/%s/resume" % c["claim_id"], token=tok)
    r = settle(tok, c["claim_id"])
    print("   after the citizen grants consent again, resume -> status=%s, steps done=%d/8" % (r["status"], sum(1 for x in r["pipeline_steps"] if x["status"] == "done")))
    assert r["status"] == "needs_more_proof"
    return "with_officer (ledger blocked + logged) -> consent granted -> resume completes"


def s6(t):
    outage(True)
    tok = login("s6-idown")
    c = file_claim(tok)
    show(c)
    print("   identity_lookup: %s - %s" % (steps(c)["identity_lookup"]["status"], steps(c)["identity_lookup"]["detail"]))
    assert c["status"] == "with_officer" and steps(c)["identity_lookup"]["status"] == "failed"
    outage(False)
    call("POST", "/claims/%s/resume" % c["claim_id"], token=tok)
    r = settle(tok, c["claim_id"])
    print("   service back, resume -> status=%s, steps done=%d/8" % (r["status"], sum(1 for x in r["pipeline_steps"] if x["status"] == "done")))
    assert r["status"] == "needs_more_proof" and all(x["status"] == "done" for x in r["pipeline_steps"])
    return "with_officer (paused at identity_lookup) -> service back -> resume completes"


def s7(t):
    tok = login("s7-autohandle")
    s, b = call("POST", "/claims", {"intent": "payment_check", "month": "2026-10"}, tok)
    assert s == 202, "POST /claims -> %s %s" % (s, b)
    c = settle(tok, b["claim_id"])
    show(c)
    d = c["decision"]
    print("   explanation: " + c["explanation_en"])
    s, a = call("GET", "/audit?entity=case&entity_id=%s&action=payment.release" % c["case_id"], token=t["admin"])
    print("   payment entries for this case: %d (nothing is paid, no officer is involved)" % a["total"])
    assert c["status"] == "closed" and d["action"] == "auto_handle" and d["decided_by"] == "ai" and d["confidence"] >= 0.9
    assert d["trace"]["payment_needed"] is False and d["trace"]["flags"] == [] and a["total"] == 0
    return "closed: AI auto_handle (confidence %.2f), ledger confirms PKR 12000 paid, no payment, no officer" % d["confidence"]


def main():
    s, h = call("GET", "/health")
    if s != 200:
        raise SystemExit("backend not healthy: %s %s" % (s, h))
    if h["mocks"]["mode"] != "fake":
        # Real mocks serve the same people (mocks/app/data is generated from demo_people.json). The script reaches them from the host.
        MOCKS["url"] = os.environ.get("MOCKS_HOST_URL", "http://localhost:8001").rstrip("/")
        urllib.request.urlopen(urllib.request.Request(MOCKS["url"] + "/reset", method="POST"), timeout=10).read()
        print("Using the REAL mocks at %s (%s)\n" % (MOCKS["url"], h["mocks"].get("url")))
    t = {"admin": login("admin", "admin-demo-123")}
    s, r = call("POST", "/admin/demo/reset", {"include_rules": True}, t["admin"])
    assert s == 200, "reset failed: %s %s" % (s, r)
    print("RESET: deleted %s | seeded %s\n" % (sum(r["deleted"].values()), r["seeded"]))
    results = []
    for n, (title, fn) in enumerate([("Clean approval", s1), ("Misspelled name (ask more)", s2), ("Short payment by a bad agent (officer)", s3),
                                     ("Duplicate claim, same month (officer)", s4), ("Consent withdrawn (blocked and logged)", s5),
                                     ("Identity service down (paused, then resume)", s6),
                                     ("Auto-handled: payment check, nothing owed", s7)], start=1):
        print("SCENARIO %d: %s" % (n, title))
        try:
            outcome = fn(t)
            results.append((n, title, True, outcome))
            print("   => PASS: %s\n" % outcome)
        except AssertionError as e:
            results.append((n, title, False, str(e)))
            print("   => FAIL: %s\n" % e)
    call("POST", "/admin/demo/chaos", {"identity_down": False, "ledger_down": False, "payments_down": False}, t["admin"])
    if MOCKS["url"]:
        outage(False)
    print("SUMMARY")
    for n, title, ok, outcome in results:
        print("  %d. %-46s %s  %s" % (n, title, "PASS" if ok else "FAIL", outcome))
    raise SystemExit(0 if all(r[2] for r in results) else 1)


if __name__ == "__main__":
    main()
