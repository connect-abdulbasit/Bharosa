from datetime import timedelta

from app.models import Case
from app.models.base import utcnow
from tests.conftest import auth


def test_queue_includes_short_ai_reason(client):
    items = client.get("/queue", headers=auth(client, "officer")).json()["items"]
    top = items[0]
    assert top["case_id"] == "case-0001" and top["recommended_action"] == "send_to_human"
    assert top["ai_reason"].startswith("Ledger shows PKR 8000") and top["reasons"][0] == top["ai_reason"]
    assert {i["case_id"] for i in items} == {"case-0001", "case-0002"}  # with_officer + needs_more_proof only


def test_queue_sorts_risk_then_confidence_then_age(client, db):
    now = utcnow()
    for cid, risk, conf, age_h in (("case-0001", 0.5, 0.5, 1), ("case-0002", 0.5, 0.5, 9), ("case-0004", 0.5, 0.4, 2)):
        c = db.get(Case, cid)
        c.risk_score, c.confidence, c.status, c.updated_at = risk, conf, "with_officer", now - timedelta(hours=age_h)
    db.commit()
    ids = [i["case_id"] for i in client.get("/queue", headers=auth(client, "officer")).json()["items"]]
    assert ids == ["case-0004", "case-0002", "case-0001"]  # lowest confidence first, then the one waiting longest


def test_queue_is_not_for_citizens_or_helpers(client):
    for who in ("citizen", "helper", "auditor"):
        assert client.get("/queue", headers=auth(client, who)).status_code == 403


def test_families_show_latest_case_status_and_only_linked(client):
    items = {i["head_name"]: i for i in client.get("/helper/families", headers=auth(client, "helper")).json()["items"]}
    assert len(items) == 10
    assert items["Muhammad Aslam"]["latest_case_status"] == "with_officer"
    assert items["Zubaida Khatoon"]["latest_case_status"] == "needs_more_proof"
    assert items["Gul Bano"]["latest_case_status"] == "approved"
    assert items["Fatima Bibi"]["latest_case_status"] == "submitted"
    assert items["Allah Ditta"]["latest_case_status"] is None and items["Allah Ditta"]["last_action"] == "No cases yet"
    assert "Rashid Mehmood" not in items
