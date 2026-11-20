"""Seed demo data (ALL FAKE). Run: make seed   (or: python -m app.seed [--reset])

Creates: one user per role, a helper linked to 10 citizens (fake names with spelling variants, fake CNICs
starting 00000), one unlinked citizen, 5 sample cases in different statuses, rule "stipend_short_payment" v1
(auto >= 0.90, ask_more >= 0.60) and default consents (identity, payments, complaints, notifications).
Idempotent: does nothing if users already exist (use --reset in development to wipe and reseed).
"""
import sys
from datetime import timedelta
from typing import Dict, List, Tuple

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.config import settings
from app.models import (Base, Case, Claim, Consent, ConsentEvent, Decision, Family, Rule,
                        RuleVersion, User)
from app.models.base import utcnow
from app.services import audit
from app.services.consent import DEFAULT_RECIPIENT
from app.services.rules import DEFAULT_LOGIC, DEFAULT_THRESHOLDS, RULE_ID
from contracts.enums import ConsentScope

# (user id, username, name, cnic suffix) citizens linked to the helper. u-citizen-1 is the demo citizen.
LINKED: List[Tuple[str, str, str, str]] = [
    ("u-citizen-1", "citizen", "Fatima Bibi", "002"),
    ("u-citizen-2", "citizen02", "Muhammad Aslam", "001"),
    ("u-citizen-3", "citizen03", "Zubaida Khatoon", "003"),
    ("u-citizen-4", "citizen04", "Gul Bano", "004"),
    ("u-citizen-5", "citizen05", "Mohammad Rafiq", "006"),
    ("u-citizen-6", "citizen06", "Shaista Parveen", "007"),
    ("u-citizen-7", "citizen07", "Mumtaz Begum", "008"),
    ("u-citizen-8", "citizen08", "Muhammed Yaqoob", "009"),
    ("u-citizen-9", "citizen09", "Rukhsana Kausar", "010"),
    ("u-citizen-10", "citizen10", "Allah Ditta", "011"),
]
UNLINKED = ("u-citizen-11", "citizen11", "Rashid Mehmood", "005")  # shopkeeper, not linked to the helper
STAFF = [
    ("u-helper-1", "helper", "Nasreen Akhtar (demo helper)", "helper"),
    ("u-officer-1", "officer", "Officer Imran (demo)", "officer"),
    ("u-admin-1", "admin", "Admin (demo)", "admin"),
    ("u-auditor-1", "auditor", "Auditor (demo)", "auditor"),
]
SCOPES = [s.value for s in ConsentScope]


def cnic(suffix: str) -> str:
    return "0000042101" + suffix  # 13 digits, starts 00000, FAKE


def run(db: Session, reset: bool = False) -> Dict[str, int]:
    if reset:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    if db.query(User).count() > 0:
        return {"skipped": 1}

    pw = settings.DEMO_PASSWORDS
    hashes = {p: hash_password(p) for p in set(pw.values())}
    for i, (uid, uname, name, role) in enumerate(STAFF, start=1):
        db.add(User(id=uid, username=uname, name=name, phone="030000000%02d" % i, role=role, password_hash=hashes[pw[role]]))
    for i, (uid, uname, name, suffix) in enumerate(LINKED + [UNLINKED], start=1):
        db.add(User(id=uid, username=uname, name=name, phone="031100000%02d" % i, cnic=cnic(suffix), role="citizen",
                    password_hash=hashes[pw["citizen"]]))
    db.flush()

    for i, (uid, *_rest) in enumerate(LINKED, start=1):
        db.add(Family(id="fam-%03d" % i, helper_id="u-helper-1", citizen_id=uid))

    db.add(Rule(id=RULE_ID, name="stipend_short_payment", active_version=1))
    db.flush()
    db.add(RuleVersion(rule_id=RULE_ID, version=1, logic=DEFAULT_LOGIC, thresholds=DEFAULT_THRESHOLDS,
                       created_by="u-admin-1", note="Initial thresholds: auto >= 0.90, ask_more >= 0.60"))

    for uid in [u[0] for u in LINKED] + [UNLINKED[0]]:
        for scope in SCOPES:
            cid = "con-%s-%s" % (uid, scope)
            db.add(Consent(id=cid, citizen_id=uid, scope=scope, granted_to=DEFAULT_RECIPIENT[scope], status="granted"))
            db.flush()
            db.add(ConsentEvent(consent_id=cid, action="grant", actor_id=uid, reason="default consent (seed)"))

    now = utcnow()
    cases = [
        # id, citizen, created_by, assigned, status, priority, risk, conf, claim(type, expected, received, month), decision
        ("case-0001", "u-citizen-2", "u-helper-1", None, "with_officer", "high", 0.72, 0.58, ("short_paid", 12000, 8000, "2026-10"),
         ("send_to_human", ["Ledger shows PKR 8000 paid, programme amount is PKR 12000", "Name matched with a spelling variant (Mohammad/Muhammad)"])),
        ("case-0002", "u-citizen-3", "u-citizen-3", "u-officer-1", "needs_more_proof", "normal", 0.35, 0.71, ("missing", 12000, 0, "2026-10"),
         ("ask_more", ["ID photo slightly blurred"])),
        ("case-0003", "u-citizen-4", "u-helper-1", "u-officer-1", "approved", "normal", 0.10, 0.93, ("missing", 12000, 0, "2026-09"),
         ("auto_handle", ["Confidence 0.93 >= 0.90 and no red flags"])),
        ("case-0004", "u-citizen-1", "u-citizen-1", None, "submitted", "normal", 0.20, 0.0, ("short_paid", 12000, 9000, "2026-10"), None),
        ("case-0005", "u-citizen-11", "u-citizen-11", "u-officer-1", "closed", "normal", 0.05, 0.95, ("missing", 12000, 0, "2026-08"),
         ("auto_handle", ["Duplicate resolved"])),
    ]
    for n, (cid, citizen, by, assigned, status, prio, risk, conf, claim, dec) in enumerate(cases):
        created = now - timedelta(days=5 - n)
        db.add(Case(id=cid, citizen_id=citizen, created_by=by, assigned_to=assigned, status=status, priority=prio,
                    risk_score=risk, confidence=conf, current_step=status, notes=[], created_at=created, updated_at=created))
        db.flush()
        db.add(Claim(case_id=cid, claim_type=claim[0], expected_amount=claim[1], received_amount=claim[2], month=claim[3],
                     transcript=None, data={"source": "seed"}))
        if dec:
            db.add(Decision(case_id=cid, action=dec[0], confidence=conf, reasons=dec[1], trace={"seed": True},
                            rule_id=RULE_ID, rule_version=1, model_version="stub-0.1", decided_by="ai"))
    db.flush()
    audit.log(db, "system", "seed", "seed.run", "system", None, after={"users": 15, "cases": 5, "rule": RULE_ID})
    db.commit()
    return {"users": db.query(User).count(), "cases": db.query(Case).count()}


def main() -> None:
    from app.db import session_factory

    reset = "--reset" in sys.argv
    with session_factory()() as db:
        print("seed:", run(db, reset=reset))



if __name__ == "__main__":
    main()
