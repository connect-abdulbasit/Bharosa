"""Demo support: 6 named scenarios, 60 seeded scam checks, and a one-click reset (POST /admin/demo/reset or `python -m app.demo reset`).

Reset wipes cases, claims, decisions, jobs, photos, checked messages and consent changes, restores the seeded users
(names, phones, PINs) and re-seeds everything. Rules (and their version history) are untouched unless include_rules=True.
The audit log is NEVER wiped (it is append-only); the reset itself is audited.
"""
import hashlib
import random
import sys
from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app import demo_data, seed
from app.auth.passwords import hash_password
from app.config import settings
from app.models import (Case, CheckedMessage, Claim, Consent, ConsentEvent, Decision, Document, DocumentBlob, Family, Job,
                        Rule, RuleVersion, User)
from app.models.base import utcnow
from app.services import audit, events
from app.services.rules import RULE_ID

SCENARIOS = demo_data.SCENARIOS
SCAM_CHECKS_TOTAL = sum(n for _, n in demo_data.SCAM_AREAS)
WIPE_ORDER = (Job, Decision, DocumentBlob, Document, Claim, Case, CheckedMessage, ConsentEvent, Consent)  # children before parents


def _scenario_users(db: Session) -> None:
    pw = hash_password(settings.DEMO_PASSWORDS["citizen"])
    pin = hash_password(settings.DEMO_CITIZEN_PIN)
    for s in SCENARIOS:
        u = db.get(User, s["user_id"])
        if u is None:
            db.add(User(id=s["user_id"], username=s["username"], name=s["name"], phone="031200000%02d" % s["n"], cnic=s["cnic"],
                        role="citizen", password_hash=pw, pin_hash=pin))
        else:
            u.name, u.phone, u.cnic, u.pin_hash = s["name"], "031200000%02d" % s["n"], s["cnic"], pin
        i = demo_data.FIRST_SCENARIO_FAMILY + s["n"] - 1
        if db.get(Family, "fam-%03d" % i) is None:
            db.flush()
            db.add(Family(id="fam-%03d" % i, helper_id="u-helper-1", citizen_id=s["user_id"]))
    db.flush()


def _scenario_consents(db: Session) -> None:
    for s in SCENARIOS:
        fresh = db.get(Consent, "con-%s-identity" % s["user_id"]) is None
        seed.seed_consents(db, [s["user_id"]])
        if fresh and s.get("withdrawn"):  # scenario 5: the payments consent starts WITHDRAWN
            c = db.get(Consent, "con-%s-%s" % (s["user_id"], s["withdrawn"]))
            c.status = "withdrawn"
            db.add(ConsentEvent(consent_id=c.id, action="withdraw", actor_id=s["user_id"], reason="seeded: withdrawn for the consent demo"))
    db.flush()


def _scenario_cases(db: Session) -> None:
    now = utcnow()
    for s in SCENARIOS:
        cid = s.get("open_case")
        if not cid or db.get(Case, cid) is not None:
            continue
        db.add(Case(id=cid, citizen_id=s["user_id"], created_by="u-helper-1", assigned_to=None, status="needs_more_proof", priority="normal",
                    risk_score=0.3, confidence=0.81, current_step="needs_more_proof", notes=[], created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2)))
        db.flush()
        db.add(Claim(case_id=cid, claim_type="missing", expected_amount=12000, received_amount=0, month="2026-10", data={"source": "demo"}))
        db.add(Decision(case_id=cid, action="ask_more", confidence=0.81, reasons=["Confidence 0.81 is between 0.60 and 0.90: need more proof"],
                        trace={"seed": True}, rule_id=RULE_ID, rule_version=1, model_version="stub-0.1", decided_by="ai"))
    db.flush()


def _scam_checks(db: Session) -> None:
    """60 FAKE scam checks (no real text: a hash of a counter) across fictional areas and the last 14 days."""
    if db.query(CheckedMessage).count() > 0:
        return
    rnd = random.Random(2026)
    now = utcnow()
    i = 0
    for area, n in demo_data.SCAM_AREAS:
        for _ in range(n):
            i += 1
            sender = rnd.choice(demo_data.SCAM_SENDERS)
            reasons = []
            if sender == "9O9O":
                reasons.append("Sender '9O9O' looks like the official code '9090' but is not it (look-alike).")
            else:
                reasons.append("Sender '%s' is not the official code 9090" % sender)
            for cue in rnd.sample(demo_data.SCAM_CUES, rnd.choice([1, 1, 2])):
                reasons.append("Contains suspicious cue '%s'" % cue)
            db.add(CheckedMessage(text_hash=hashlib.sha256(("demo-scam-%d" % i).encode()).hexdigest(), label="scam",
                                  confidence=round(rnd.uniform(0.9, 0.99), 2), reasons=reasons, sender=sender, area=area,
                                  created_at=now - timedelta(days=rnd.randint(0, 13), hours=rnd.randint(0, 23))))
    db.flush()


def seed_scenarios(db: Session) -> bool:
    """Idempotent. Adds the 6 scenario citizens (linked to the helper), their consents, the duplicate-claim case and 60 scam checks."""
    _scenario_users(db)
    _scenario_consents(db)
    _scenario_cases(db)
    _scam_checks(db)
    db.commit()
    return True


def reset(db: Session, actor: User, include_rules: bool = False) -> Dict[str, Any]:
    deleted: Dict[str, int] = {}
    for model in WIPE_ORDER:
        deleted[model.__tablename__] = db.execute(delete(model)).rowcount or 0
    if include_rules:  # decisions are already gone, so nothing references the rules
        deleted["rule_versions"] = db.execute(delete(RuleVersion)).rowcount or 0
        deleted["rules"] = db.execute(delete(Rule)).rowcount or 0
    db.flush()
    seed.seed_users(db)
    seed.seed_families(db)
    seed.seed_rule(db)
    seed.seed_consents(db, [u[0] for u in seed.LINKED] + [seed.UNLINKED[0]])
    seed.seed_cases(db)
    _scenario_users(db)
    _scenario_consents(db)
    _scenario_cases(db)
    _scam_checks(db)
    from app.fake_mocks_client import reset_state

    reset_state()  # fake mocks: payments made + chaos switches
    from app.fake_mocks_client import CHAOS
    from app.services.mocks_client import push_real_chaos

    push_real_chaos(CHAOS)  # the real mocks service: switch every outage off too
    events.EMITTED.clear()
    seeded = {"cases": db.query(Case).count(), "consents": db.query(Consent).count(), "scenarios": len(SCENARIOS),
              "scam_checks": db.query(CheckedMessage).count()}
    audit.log(db, "user", actor.id, "demo.reset", "system", None, after={"deleted": deleted, "seeded": seeded, "include_rules": include_rules,
                                                                          "audit_log": "kept (append-only)"})
    db.commit()
    return {"reset": True, "include_rules": include_rules, "deleted": deleted, "seeded": seeded}


def main() -> None:
    """python -m app.demo reset [--rules]"""
    from app.db import session_factory

    if len(sys.argv) < 2 or sys.argv[1] != "reset":
        print("usage: python -m app.demo reset [--rules]   (--rules also restores rule v1 and drops the rule version history)")
        raise SystemExit(2)
    with session_factory()() as db:
        admin = db.get(User, "u-admin-1")
        if admin is None:
            raise SystemExit("no seeded admin user: run `make seed` first")
        print(reset(db, admin, include_rules="--rules" in sys.argv))


if __name__ == "__main__":
    main()
