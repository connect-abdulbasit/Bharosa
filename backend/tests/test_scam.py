from sqlalchemy import select

import bharosa_ai
from app.models import AuditLog, CheckedMessage
from contracts.ai_interface import MessageVerdict
from contracts.enums import MessageLabel
from tests.conftest import auth

SCAM_TEXT = "Pay fee at http://bit.ly/x to get your relief money urgent"


def check(client, text, sender, who="citizen", **extra):
    return client.post("/messages/check", json=dict({"text": text, "sender": sender}, **extra), headers=auth(client, who))


def test_scam_from_unofficial_sender(client, mocks):
    r = check(client, SCAM_TEXT, "SAHARA-INFO")
    b = r.json()
    assert r.status_code == 200 and b["label"] == "scam" and b["confidence"] >= 0.9 and b["official_sender"] is False
    assert b["reasons"] and "9090" in b["explanation_en"] and "9090" in b["explanation_ur"] and b["model_version"]
    assert mocks.calls == ["senders"]


def test_genuine_from_official_sender(client, mocks):
    b = check(client, "Your stipend for October is ready", "9090").json()
    assert b["label"] == "genuine" and b["official_sender"] is True and b["confidence"] >= 0.9


def test_lookalike_sender_is_a_scam_even_with_innocent_text(client, mocks):
    b = check(client, "Your stipend is ready", "9O9O").json()  # letter O instead of zero
    assert b["label"] == "scam" and b["confidence"] >= 0.9 and any("look-alike" in x for x in b["reasons"])


def test_unofficial_sender_can_never_be_called_genuine(client, mocks, monkeypatch):
    monkeypatch.setattr(bharosa_ai, "classify_message", lambda t, s: MessageVerdict(
        label=MessageLabel.genuine, confidence=0.99, reasons=["looks fine"], model_version="t"))
    b = check(client, "hello", "5555").json()
    assert b["label"] == "unsure" and b["confidence"] <= 0.6 and any("not on the official list" in x for x in b["reasons"])


def test_sender_list_down_never_claims_official(client, mocks):
    mocks.fail = {"senders"}
    b = check(client, "Your stipend is ready", "9090").json()
    assert b["official_sender"] is False and b["label"] == "unsure"  # stub said genuine; we cannot confirm the sender
    assert any("could not check the official sender list" in x for x in b["reasons"])


def test_every_check_is_stored_without_the_text(client, db, mocks):
    check(client, SCAM_TEXT, "SAHARA-INFO", area="Malir")
    check(client, SCAM_TEXT.upper() + "  ", "SAHARA-INFO")
    rows = db.execute(select(CheckedMessage)).scalars().all()
    assert len(rows) == 2 and rows[0].label == "scam" and rows[0].sender == "SAHARA-INFO" and rows[0].area == "Malir"
    assert rows[0].text_hash == rows[1].text_hash and len(rows[0].text_hash) == 64 and rows[0].created_at
    assert "bit.ly" not in str([(r.text_hash, r.reasons, r.sender) for r in rows]).replace("Contains suspicious cue 'bit.ly'", "")
    a = db.execute(select(AuditLog).where(AuditLog.action == "ai.classify_message")).scalars().all()
    assert len(a) == 2 and a[0].actor_type == "ai" and a[0].after["model_version"] and "text" not in a[0].after


def test_only_citizens_and_helpers(client, mocks):
    assert check(client, "x", "y", who="helper").status_code == 200
    for who in ("officer", "admin", "auditor"):
        assert check(client, "x", "y", who=who).status_code == 403
