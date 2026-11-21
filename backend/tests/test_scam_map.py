from app.models import CheckedMessage
from app.services.scam_map import normalise_reason
from tests.conftest import auth

LEAKS = ("SAHARA-INFO", "9O9O", "RELIEF-PAY", "SAHARA-lNFO", "0300-0000000", "GOV-RELIEF", "text_hash", "text", "user", "sender")


def smap(client, who="officer", **params):
    return client.get("/scam-map", params=params, headers=auth(client, who))


def test_roles(client, demo):
    for who in ("officer", "admin", "auditor"):
        assert smap(client, who).status_code == 200
    for who in ("citizen", "helper"):
        assert smap(client, who).status_code == 403
    assert client.get("/scam-map").status_code == 401
    assert smap(client, days=0).status_code == 422 and smap(client, days=91).status_code == 422


def test_counts_by_area_with_small_groups_folded_into_other(client, demo):
    b = smap(client).json()
    assert b["total"] == 60 and b["min_group_size"] == 3 and b["window_days"] == 30
    areas = {a["area"]: a["count"] for a in b["by_area"]}
    assert areas == {"Noorabad": 18, "Sahil Colony": 14, "Bagh-e-Zubaida": 10, "Mehran Town North": 8, "Kausar Basti": 6, "other": 4}  # 2 + 2 folded
    assert "Tiny Village" not in areas and "unknown" not in areas
    assert all(n >= 3 for n in areas.values()) and sum(areas.values()) == 60
    assert b["by_area"][-1]["area"] == "other"  # 'other' always last


def test_counts_by_day_cover_the_window(client, demo):
    b = smap(client).json()
    assert len(b["by_day"]) == 30 and sum(d["count"] for d in b["by_day"]) == 60
    days = [d["day"] for d in b["by_day"]]
    assert days == sorted(days) and sum(1 for d in b["by_day"] if d["count"] > 0) >= 10  # spread over ~14 days
    week = smap(client, days=7).json()
    assert len(week["by_day"]) == 7 and 0 < week["total"] < 60


def test_counts_by_reason_use_fixed_categories_only(client, demo):
    b = smap(client).json()
    reasons = {r["reason"] for r in b["by_reason"]}
    assert "Sender is not the official code" in reasons and "Sender looks like the official code (look-alike)" in reasons
    assert all(r.startswith(("Sender", "Suspicious wording:", "other", "Other")) for r in reasons)
    assert all(r["count"] >= 3 for r in b["by_reason"])


def test_no_message_text_sender_or_user_id_ever_leaves(client, demo):
    r = smap(client)
    assert set(r.json()) == {"generated_at", "window_days", "min_group_size", "total", "by_area", "by_day", "by_reason"}
    assert all(set(x) == {"area", "count"} for x in r.json()["by_area"]) and all(set(x) == {"day", "count"} for x in r.json()["by_day"])
    for leak in LEAKS[:6] + ("text_hash", "u-demo", "u-citizen", "http://"):
        assert leak not in r.text, leak


def test_new_checks_appear_once_an_area_has_three_reports(client, demo):
    h = auth(client, "citizen")
    send = lambda: client.post("/messages/check", json={"text": "Pay fee at http://bit.ly/x urgent", "sender": "SAHARA-INFO", "area": "Lyari Test"}, headers=h)  # noqa: E731
    for _ in range(2):
        send()
    areas = {a["area"]: a["count"] for a in smap(client).json()["by_area"]}
    assert "Lyari Test" not in areas and areas["other"] == 6                       # 2 new reports hidden inside 'other'
    send()
    areas = {a["area"]: a["count"] for a in smap(client).json()["by_area"]}
    assert areas["Lyari Test"] == 3 and areas["other"] == 4


def test_only_scam_verdicts_count(client, demo, db):
    h = auth(client, "citizen")
    client.post("/messages/check", json={"text": "Your stipend is ready", "sender": "9090", "area": "Noorabad"}, headers=h)  # genuine
    assert smap(client).json()["total"] == 60
    assert db.query(CheckedMessage).count() == 61


def test_rare_reasons_are_folded_too(client, demo, db):
    from app.models.base import utcnow

    db.add(CheckedMessage(text_hash="x" * 64, label="scam", confidence=0.9, reasons=["Something very unusual about this one"], sender="X", area="Noorabad", created_at=utcnow()))
    db.commit()
    reasons = {r["reason"]: r["count"] for r in smap(client).json()["by_reason"]}
    assert reasons.get("other", 0) >= 1 and not any("unusual" in k for k in reasons)


def test_reason_normalisation_never_keeps_sender_names():
    assert normalise_reason("Sender 'RELIEF-PAY' is not the official code 9090") == "Sender is not the official code"
    assert normalise_reason("Sender '9O9O' looks like the official code '9090' but is not it (look-alike).") == "Sender looks like the official code (look-alike)"
    assert normalise_reason("Contains suspicious cue 'bit.ly'") == "Suspicious wording: bit.ly"
    assert normalise_reason("Call 0300-1234567 now") == "Other"
    assert normalise_reason("We could not check the official sender list right now, so we cannot confirm this sender.") == "Sender could not be verified"


def test_empty_database_is_fine(client):
    b = smap(client).json()
    assert b["total"] == 0 and b["by_area"] == [] and b["by_reason"] == [] and len(b["by_day"]) == 30
