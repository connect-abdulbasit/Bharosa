"""Digital Twin: see what a proposed rule would have done BEFORE the admin publishes it, and how the system handles a scam wave.

Public API only (admin login). Read-only by default: the one write is the backend's own `rule.simulate` audit row.
`--seed-history` is opt-in: it files claims as the 7 demo citizens to create past decisions (writes demo data).

    PYTHONPATH=. python -m services.digital_twin.twin --auto-handle-min 0.8 [--ask-more-min 0.6] [--seed-history] [--scam-wave]
Env: BASE (default http://localhost:8000), TWIN_ADMIN / TWIN_ADMIN_PASSWORD (fake demo login).
"""
import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx

OVERSIGHT = {"send_to_human": 0, "ask_more": 1, "auto_handle": 2}  # higher = less human involvement
DEMO_CITIZENS = ["s1-clean", "s2-spelling", "s3-shortpay", "s4-duplicate", "s5-consent", "s6-idown", "s7-autohandle"]
PW = "citizen-demo-123"  # FAKE demo password
SAY, SHORT = {"transcript": "mujhe is mahine ke paisay nahi mile"}, {"transcript": "mujhe paisay kam mile hain"}
def _names() -> Dict[str, str]:
    """username -> the name that person says (contracts/fixtures/demo_people.json); {} when the file is not there."""
    from pathlib import Path

    try:
        path = Path(__file__).resolve().parent.parent.parent / "contracts" / "fixtures" / "demo_people.json"
        return {p["username"]: p["name"] for p in json.loads(path.read_text(encoding="utf-8"))["people"]}
    except (OSError, ValueError, KeyError):
        return {}


NAMES = _names()
BODY = {"s3-shortpay": SHORT, "s7-autohandle": {"intent": "payment_check", "month": "2026-10"}}  # the others: "nothing was paid"

# Scam wave: (sender, text, truth). Official sender is the fictional short code 9090; the rest are lookalikes/unknown.
WAVE = [
    ("9O9O", "Mubarak! Aap ka Sahara inam nikla hai. 2000 rupay fee bhej kar code batayen: http://sahara-claim.biz", "scam"),
    ("RELIEF-PAY", "URGENT: your relief payment is blocked. Send your CNIC and the 6 digit code now or lose PKR 12000", "scam"),
    ("0300-0000000", "آپ کی امدادی رقم رک گئی ہے۔ فوراً 500 روپے ایزی پیسہ کریں", "scam"),
    ("SAHARA-lNFO", "Sahara Relief: click http://bit.ly/sahara-pay to verify your account today, otherwise it closes", "scam"),
    ("GOV-RELIEF", "Aap ki qist tayyar hai. Agent ko 1000 rupay dein, phir paisay milenge. Jaldi karein!", "scam"),
    ("9090", "Sahara Relief Programme: your October payment of PKR 12000 was sent on 05-10-2026. Questions: call 9090.", "genuine"),
    ("9090", "Aap ki Sahara Relief ki qist PKR 12000 bhej di gayi hai. Koi fees nahi hai. Madad ke liye 9090.", "genuine"),
    ("9090-SAHARA", "Reminder: bring your ID card to the nearest registered centre. No payment is ever asked over SMS.", "genuine"),
    ("SAHARA-HELP", "آپ کا کیس درج ہو گیا ہے۔ ہم جلد اطلاع دیں گے۔ کوئی رقم یا کوڈ نہ دیں۔", "genuine"),
    ("9091", "Your claim case-0001 is with an officer. We will update you in 3 days.", "genuine"),
]


def assess(sim: Dict[str, Any]) -> Dict[str, Any]:
    """Turn the backend's simulation into what an admin needs to decide: who loses or gains human oversight."""
    less = more = 0
    for transition, n in sim.get("by_transition", {}).items():
        old, new = (x.strip() for x in transition.split("->"))
        if OVERSIGHT[new] > OVERSIGHT[old]:
            less += n
        else:
            more += n
    if sim["simulated_cases"] == 0:
        verdict = "NO DATA: no past decision has stored inputs. Run with --seed-history (demo) or wait for real cases."
    elif sim["would_change"] == 0:
        verdict = "SAFE on history: no past decision would change."
    elif less:
        verdict = "REVIEW BEFORE PUBLISHING: %d past case(s) would get LESS human oversight." % less
    else:
        verdict = "TIGHTER: %d past case(s) would go to a human instead (extra officer workload); none lose oversight." % more
    return {"proposed": sim["proposed"], "current_version": sim["current_version"], "cases_replayed": sim["simulated_cases"],
            "skipped_no_inputs": sim["skipped_no_inputs"], "would_change": sim["would_change"], "by_transition": sim["by_transition"],
            "less_human_oversight": less, "more_human_oversight": more, "examples": sim["examples"][:5], "verdict": verdict}


def score_wave(results: List[Dict[str, str]]) -> Dict[str, Any]:
    """results: [{truth, label}] -> honest counts. `unsure` is never counted as a catch."""
    scams = [r for r in results if r["truth"] == "scam"]
    real = [r for r in results if r["truth"] == "genuine"]
    return {"messages": len(results), "scams_caught": sum(r["label"] == "scam" for r in scams),
            "scams_unsure": sum(r["label"] == "unsure" for r in scams), "scams_missed": sum(r["label"] == "genuine" for r in scams),
            "genuine_blocked_by_mistake": sum(r["label"] == "scam" for r in real),
            "genuine_unsure": sum(r["label"] == "unsure" for r in real)}


class Twin:
    def __init__(self, base: str):
        self.base, self.http, self.tokens = base.rstrip("/"), httpx.Client(timeout=60), {}

    def call(self, method: str, path: str, user: Optional[str] = None, **kw: Any) -> Dict[str, Any]:
        headers = {"Authorization": "Bearer " + self.tokens[user]} if user else {}
        r = self.http.request(method, self.base + path, headers=headers, **kw)
        if r.status_code >= 400:
            raise RuntimeError("%s %s -> %s %s" % (method, path, r.status_code, r.text[:200]))
        return r.json()

    def login(self, user: str, password: str) -> None:
        self.tokens[user] = self.call("POST", "/auth/login", json={"username": user, "password": password})["access_token"]

    def seed_history(self) -> int:
        """Opt-in: one claim per demo citizen so there are past decisions with stored inputs. Skips citizens that already have one."""
        n = 0
        for user in DEMO_CITIZENS:
            self.login(user, PW)
            body = BODY.get(user, SAY)
            if "transcript" in body and user in NAMES:  # the real extractor refuses speech without a name; the stub ignores it
                body = dict(body, transcript="mera naam %s hai. %s" % (NAMES[user], body["transcript"]))
            try:
                claim = self.call("POST", "/claims", user, json=body)
            except RuntimeError:
                continue  # already filed this month
            for _ in range(300):
                if not self.call("GET", "/claims/%s/progress" % claim["claim_id"], user)["active"]:
                    break
                time.sleep(0.1)
            n += 1
        return n

    def preview(self, admin: str, auto_handle_min: float, ask_more_min: float) -> Dict[str, Any]:
        rule_id = self.call("GET", "/rules", admin)["items"][0]["id"]
        return assess(self.call("POST", "/rules/%s/simulate" % rule_id, admin,
                                json={"auto_handle_min": auto_handle_min, "ask_more_min": ask_more_min}))

    def scam_wave(self) -> Dict[str, Any]:
        self.login("citizen", PW)
        results = []
        for sender, text, truth in WAVE:
            r = self.call("POST", "/messages/check", "citizen", json={"text": text, "sender": sender})
            results.append({"truth": truth, "label": r["label"], "sender": sender, "confidence": r["confidence"], "reasons": r["reasons"][:2]})
        return dict(score_wave(results), detail=results)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auto-handle-min", type=float, required=True)
    ap.add_argument("--ask-more-min", type=float, default=0.6)
    ap.add_argument("--seed-history", action="store_true", help="file demo claims first (writes demo data)")
    ap.add_argument("--scam-wave", action="store_true")
    ap.add_argument("--out", default="twin_report.json")
    a = ap.parse_args()
    t = Twin(os.environ.get("BASE", "http://localhost:8000"))
    admin = os.environ.get("TWIN_ADMIN", "admin")
    t.login(admin, os.environ.get("TWIN_ADMIN_PASSWORD", "admin-demo-123"))
    report: Dict[str, Any] = {"simulated": True}
    if a.seed_history:
        report["history_claims_added"] = t.seed_history()
    report["rule_preview"] = t.preview(admin, a.auto_handle_min, a.ask_more_min)
    if a.scam_wave:
        report["scam_wave"] = t.scam_wave()
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    p = report["rule_preview"]
    print("RULE PREVIEW  auto_handle>=%.2f ask_more>=%.2f (current v%d)" % (a.auto_handle_min, a.ask_more_min, p["current_version"]))
    print("  replayed %d case(s), %d would change %s" % (p["cases_replayed"], p["would_change"], p["by_transition"] or ""))
    print("  " + p["verdict"])
    if a.scam_wave:
        w = report["scam_wave"]
        print("SCAM WAVE  %(messages)d messages: caught %(scams_caught)d, unsure %(scams_unsure)d, missed %(scams_missed)d, "
              "real messages blocked by mistake %(genuine_blocked_by_mistake)d" % w)
    print("  full report: " + a.out)


if __name__ == "__main__":
    main()
