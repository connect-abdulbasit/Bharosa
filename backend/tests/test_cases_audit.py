from sqlalchemy import select

from app.models import AuditLog
from tests.conftest import CITIZEN1, auth


def rows_for(db, case_id):
    return db.execute(select(AuditLog).where(AuditLog.entity == "case", AuditLog.entity_id == case_id).order_by(AuditLog.id)).scalars().all()


def test_every_status_change_creates_an_audit_row(client, db):
    c = auth(client, "citizen")
    created = client.post("/cases", json={"claim_type": "short_paid", "amount_claimed_pkr": 4000, "notes": "paid less"}, headers=c)
    assert created.status_code == 200
    cid = created.json()["id"]
    assert created.json()["status"] == "submitted" and created.json()["amount_claimed_pkr"] == 4000

    steps = [
        ("helper", "/cases/%s/escalate" % cid, {"reason": "middleman asked for a fee"}, "submitted", "with_officer", "case.escalate"),
        ("officer", "/cases/%s/decide" % cid, {"action": "ask_more", "reason": "need clearer ID"}, "with_officer", "needs_more_proof", "case.decide"),
        ("officer", "/cases/%s/decide" % cid, {"action": "approve", "reason": "ID is fine now"}, "needs_more_proof", "approved", "case.decide"),
        ("officer", "/cases/%s/close" % cid, {"resolution": "paid"}, "approved", "closed", "case.close"),
    ]
    # helper is linked to citizen-1 who owns this case
    for role, path, body, old, new, action in steps:
        r = client.post(path, json=body, headers=auth(client, role))
        assert r.status_code == 200, (path, r.text)
        assert r.json()["status"] == new
        row = [x for x in rows_for(db, cid) if x.action == action][-1]  # approve also logs payment.release
        assert row.action == action and row.before["status"] == old and row.after["status"] == new
        assert row.actor_type == "user"

    rows = rows_for(db, cid)
    assert [r.action for r in rows if r.action != "payment.release"] == ["case.create", "case.escalate", "case.decide", "case.decide", "case.close"]
    assert rows[0].before is None and rows[0].after["status"] == "submitted"


def test_invalid_transition_is_409_and_not_audited(client, db):
    h = auth(client, "officer")
    n = len(rows_for(db, "case-0005"))
    assert client.post("/cases/case-0005/close", json={"resolution": "again"}, headers=h).status_code == 409  # already closed
    assert client.post("/cases/case-0005/decide", json={"action": "approve", "reason": "again"}, headers=h).status_code == 409
    assert len(rows_for(db, "case-0005")) == n


def test_assign_audits_and_validates(client, db):
    h = auth(client, "admin")
    r = client.post("/cases/case-0004/assign", json={"officer_id": "u-officer-1"}, headers=h)
    assert r.status_code == 200 and r.json()["assigned_to"] == "u-officer-1"
    row = rows_for(db, "case-0004")[-1]
    assert row.action == "case.assign" and row.before["assigned_to"] is None and row.after["assigned_to"] == "u-officer-1"
    assert client.post("/cases/case-0004/assign", json={"officer_id": CITIZEN1}, headers=h).status_code == 422


def test_decision_stores_rule_version_and_officer(client, db):
    r = client.post("/cases/case-0001/decide", json={"action": "reject", "note": "ledger is correct"}, headers=auth(client, "officer"))
    d = r.json()["decision"]
    assert d["rule_version"] == 1 and d["decided_by"] == "u-officer-1" and d["action"] == "reject"


def test_decide_rejects_unknown_action(client):
    r = client.post("/cases/case-0001/decide", json={"action": "pay_everyone"}, headers=auth(client, "officer"))
    assert r.status_code == 422


def test_login_and_failed_login_are_audited(client, db):
    auth(client, "citizen")
    assert client.post("/auth/login", json={"username": "citizen", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"username": "nobody", "password": "x"}).status_code == 401
    actions = [r.action for r in db.execute(select(AuditLog)).scalars()]
    assert actions.count("auth.login") == 1 and actions.count("auth.login_failed") == 2
    failed = db.execute(select(AuditLog).where(AuditLog.action == "auth.login_failed")).scalars().all()
    assert all(f.actor_type == "system" for f in failed) and "password" not in str(failed[0].after)


def test_request_id_groups_entries_and_is_returned(client, db):
    h = dict(auth(client, "citizen"), **{"X-Request-ID": "req-abc-123"})
    r = client.post("/claims", json={"transcript": "mujhe paisay kam mile hain"}, headers=h)
    assert r.headers["X-Request-ID"] == "req-abc-123"
    rows = db.execute(select(AuditLog).where(AuditLog.request_id == "req-abc-123")).scalars().all()
    assert "claim.create" in [x.action for x in rows] and len(rows) > 3  # every pipeline step shares the request id
    assert {x.actor_type for x in rows} >= {"user", "agent", "ai"}
    assert client.get("/me", headers=h).headers["X-Request-ID"] == "req-abc-123"
    assert len(client.get("/health").headers["X-Request-ID"]) >= 16  # generated


def test_audit_endpoint_filters_and_has_no_write_routes(client):
    admin = auth(client, "admin")
    client.post("/cases/case-0004/assign", json={"officer_id": "u-officer-1"}, headers=admin)
    out = client.get("/audit", params={"action": "case.assign"}, headers=admin).json()
    assert out["total"] == 1 and out["items"][0]["entity_id"] == "case-0004" and out["items"][0]["actor"] == "u-admin-1"
    for method in ("PUT", "PATCH", "DELETE"):
        assert client.request(method, "/audit", headers=admin).status_code in (404, 405)
        assert client.request(method, "/audit/1", headers=admin).status_code in (404, 405)


def test_audit_rows_are_immutable_in_orm(db):
    import pytest

    from app.models import AuditImmutable

    row = db.execute(select(AuditLog)).scalars().first()
    row.action = "tampered"
    with pytest.raises(AuditImmutable):
        db.flush()
    db.rollback()
    row = db.execute(select(AuditLog)).scalars().first()
    db.delete(row)
    with pytest.raises(AuditImmutable):
        db.flush()
    db.rollback()


def test_rule_new_version_is_immutable_history(client, db):
    admin = auth(client, "admin")
    r = client.post("/rules/rule-stipend-short-payment/versions", json={"auto_handle_min": 0.95, "ask_more_min": 0.7, "note": "stricter"}, headers=admin)
    assert r.status_code == 200 and r.json()["version"] == 2
    versions = client.get("/rules/rule-stipend-short-payment/versions", headers=admin).json()["versions"]
    assert [v["version"] for v in versions] == [2, 1] and versions[1]["auto_handle_min"] == 0.9  # v1 untouched
    assert client.get("/rules", headers=admin).json()["items"][0]["current_version"] == 2
    bad = client.post("/rules/rule-stipend-short-payment/versions", json={"auto_handle_min": 0.5, "ask_more_min": 0.9}, headers=admin)
    assert bad.status_code == 422
    d = client.post("/cases/case-0001/decide", json={"action": "approve", "reason": "checked"}, headers=auth(client, "officer")).json()["decision"]
    assert d["rule_version"] == 2


def test_api_key_shown_once_and_hashed(client, db):
    from app.models import ApiKey

    r = client.post("/apikeys", json={"name": "ngo", "scopes": ["cases:read"]}, headers=auth(client, "admin"))
    key = r.json()["key"]
    stored = db.query(ApiKey).one()
    assert key.startswith("bhr_live_") and stored.key_hash != key and key not in str(client.get("/apikeys", headers=auth(client, "admin")).json())
