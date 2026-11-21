"""A helper may GRANT consent for a citizen only with that citizen's 4-digit PIN."""
from sqlalchemy import select

from app.models import AuditLog, ConsentEvent
from tests.conftest import CITIZEN1, UNLINKED, auth

CID = "con-%s-notifications" % CITIZEN1


def withdraw_as_citizen(client):
    assert client.post("/consent/%s/withdraw" % CID, headers=auth(client, "citizen")).status_code == 200


def grant(client, **extra):
    return client.post("/consent", json=dict({"scope": "notifications", "citizen_id": CITIZEN1}, **extra), headers=auth(client, "helper"))


def test_helper_grant_without_pin_is_403(client):
    withdraw_as_citizen(client)
    r = grant(client)
    assert r.status_code == 403 and "PIN" in r.json()["message"]
    state = {i["scope"]: i["granted"] for i in client.get("/consent", headers=auth(client, "citizen")).json()["items"]}
    assert state["notifications"] is False  # nothing was granted


def test_helper_grant_with_wrong_pin_is_403_and_audited(client, db):
    withdraw_as_citizen(client)
    assert grant(client, pin="0000").status_code == 403
    assert grant(client, pin="12").status_code == 403 and grant(client, pin="abcd").status_code == 403
    fails = db.execute(select(AuditLog).where(AuditLog.action == "consent.pin_failed")).scalars().all()
    assert len(fails) == 3 and all(f.actor_id == "u-helper-1" and f.entity_id == CITIZEN1 for f in fails)
    assert "0000" not in str([f.after for f in fails])  # the guess is never logged


def test_helper_grant_with_correct_pin_records_actor_and_confirmation(client, db):
    withdraw_as_citizen(client)
    r = grant(client, pin="1234")
    assert r.status_code == 200 and r.json()["granted"] is True
    ev = db.execute(select(ConsentEvent).where(ConsentEvent.consent_id == CID).order_by(ConsentEvent.created_at)).scalars().all()[-1]
    assert ev.action == "grant" and ev.actor_id == "u-helper-1" and ev.confirmed_by == CITIZEN1
    row = db.execute(select(AuditLog).where(AuditLog.action == "consent.grant").order_by(AuditLog.id.desc())).scalars().first()
    assert row.actor_id == "u-helper-1" and row.after["confirmed_by"] == CITIZEN1


def test_pin_lockout_after_five_wrong_tries(client):
    withdraw_as_citizen(client)
    for _ in range(5):
        assert grant(client, pin="9999").status_code == 403
    assert grant(client, pin="1234").status_code == 429  # even the right PIN waits


def test_citizen_grants_for_themselves_without_a_pin(client, db):
    withdraw_as_citizen(client)
    r = client.post("/consent", json={"scope": "notifications"}, headers=auth(client, "citizen"))
    assert r.status_code == 200
    ev = db.execute(select(ConsentEvent).where(ConsentEvent.consent_id == CID).order_by(ConsentEvent.created_at)).scalars().all()[-1]
    assert ev.actor_id == CITIZEN1 and ev.confirmed_by is None


def test_helper_withdraw_and_correct_need_no_pin(client):
    h = auth(client, "helper")
    assert client.post("/consent/%s/withdraw" % CID, headers=h).status_code == 200
    assert client.post("/consent/%s/correct" % CID, json={"field": "phone", "new_value": "03005550000"}, headers=h).status_code == 200


def test_helper_cannot_grant_for_unlinked_even_with_a_pin(client):
    r = client.post("/consent", json={"scope": "identity", "citizen_id": UNLINKED, "pin": "1234"}, headers=auth(client, "helper"))
    assert r.status_code == 403 and "linked" in r.json()["message"]


def test_helper_cannot_grant_for_citizen_without_a_pin(client, db):
    from app.models import User

    db.get(User, CITIZEN1).pin_hash = None
    db.commit()
    withdraw_as_citizen(client)
    r = grant(client, pin="1234")
    assert r.status_code == 403 and "not set a PIN" in r.json()["message"]


def test_citizen_sets_a_new_pin(client):
    c = auth(client, "citizen")
    assert client.post("/me/pin", json={"pin": "4321", "password": "wrong"}, headers=c).status_code == 403
    assert client.post("/me/pin", json={"pin": "43", "password": "citizen-demo-123"}, headers=c).status_code == 422
    assert client.post("/me/pin", json={"pin": "4321", "password": "citizen-demo-123"}, headers=c).status_code == 200
    withdraw_as_citizen(client)
    assert grant(client, pin="1234").status_code == 403  # old PIN no longer works
    assert grant(client, pin="4321").status_code == 200
    assert client.post("/me/pin", json={"pin": "4321", "password": "x"}, headers=auth(client, "helper")).status_code == 403
