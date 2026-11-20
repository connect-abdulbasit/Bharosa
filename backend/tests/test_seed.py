from sqlalchemy import select

from app.models import Case, Consent, Family, Rule, RuleVersion, User


def test_seed_shape(db):
    users = db.execute(select(User)).scalars().all()
    assert {u.role for u in users} == {"citizen", "helper", "officer", "admin", "auditor"}
    assert len([u for u in users if u.role == "helper"]) == 1
    assert db.query(Family).count() == 10
    cnics = [u.cnic for u in users if u.cnic]
    assert cnics and all(c.startswith("00000") and len(c) == 13 and c.isdigit() for c in cnics)
    names = [u.name for u in users]
    assert "Muhammad Aslam" in names and "Mohammad Rafiq" in names and "Muhammed Yaqoob" in names  # spelling variants


def test_seed_cases_rule_consents(db):
    assert db.query(Case).count() == 5
    assert len({c.status for c in db.query(Case)}) == 5
    rule = db.get(Rule, "rule-stipend-short-payment")
    assert rule.name == "stipend_short_payment" and rule.active_version == 1
    rv = db.execute(select(RuleVersion).where(RuleVersion.rule_id == rule.id)).scalar_one()
    assert rv.thresholds["auto_handle_min"] == 0.90 and rv.thresholds["ask_more_min"] == 0.60
    citizens = db.query(User).filter(User.role == "citizen").count()
    assert citizens == 11 and db.query(Consent).count() == citizens * 4
    assert {c.scope for c in db.query(Consent)} == {"identity", "payments", "complaints", "notifications"}


def test_seed_is_idempotent(db):
    from app import seed

    assert seed.run(db) == {"skipped": 1}
    assert db.query(User).count() == 15
