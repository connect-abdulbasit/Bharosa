"""A payment happens once: the idempotency key (case_id:decision_id) is saved BEFORE the call and reused by every retry."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.fake_mocks_client import PAYMENTS, FakeMocksClient
from app.main import app
from app.models import AuditLog, Case, Decision
from app.services.mock_errors import MockUnavailable
from app.services.mocks_client import MocksClient
from tests.conftest import auth


def approve(client, case="case-0001", reason="Ledger shows 8000 of 12000"):
    return client.post("/cases/%s/decide" % case, json={"action": "approve", "reason": reason}, headers=auth(client, "officer"))


def approvals(db, case="case-0001"):
    return db.execute(select(Decision).where(Decision.case_id == case, Decision.action == "approve")).scalars().all()


def test_double_approval_produces_one_payment(client, db, mocks):
    assert approve(client).status_code == 200
    second = approve(client)
    assert second.status_code == 409  # already approved
    assert len(mocks.disburse_keys) == 1 and len(mocks.disbursed) == 1
    rows = approvals(db)
    assert len(rows) == 1 and rows[0].payment_status == "paid" and rows[0].payment_ref == "PAY-TEST0001"
    assert rows[0].idempotency_key == "case-0001:%s" % rows[0].id
    assert len(db.execute(select(AuditLog).where(AuditLog.action == "payment.release")).scalars().all()) == 1


def test_retry_after_a_failed_payment_reuses_the_same_key(client, db, mocks):
    mocks.fail = {"disburse"}
    assert approve(client).status_code == 503
    first = approvals(db)[0]
    assert first.payment_status == "failed" and first.payment_ref is None and first.idempotency_key
    assert db.get(Case, "case-0001").status == "with_officer"  # nothing changed
    mocks.fail = set()
    assert approve(client, reason="retry after the rail came back").status_code == 200
    db.expire_all()
    rows = approvals(db)
    assert len(rows) == 1 and rows[0].id == first.id  # the same decision, not a second one
    assert mocks.disburse_keys == [first.idempotency_key] * 2 and len(mocks.disbursed) == 1  # asked twice, paid once
    assert rows[0].payment_status == "paid" and rows[0].reasons == ["retry after the rail came back"]


def test_payment_made_but_status_change_failed_is_not_paid_twice(client, db, mocks, monkeypatch):
    """Worst case: the money moved, then the request died before the case was marked approved."""
    from app.routers import cases as cases_router

    real = cases_router.case_service.change_status
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("database went away")
        return real(*a, **k)

    monkeypatch.setattr(cases_router.case_service, "change_status", flaky)
    safe = TestClient(app, raise_server_exceptions=False)
    r = safe.post("/cases/case-0001/decide", json={"action": "approve", "reason": "approved by me"}, headers=auth(client, "officer"))
    assert r.status_code == 500 and "database went away" not in r.text
    db.expire_all()
    d = approvals(db)[0]
    assert d.payment_status == "paid" and d.payment_ref and db.get(Case, "case-0001").status == "with_officer"  # paid, not yet approved
    assert approve(client).status_code == 200  # the officer retries
    db.expire_all()
    assert len(mocks.disburse_keys) == 1  # the rail was NOT called again
    assert db.get(Case, "case-0001").status == "approved" and approvals(db)[0].payment_ref == d.payment_ref and len(approvals(db)) == 1


def test_key_is_saved_before_the_payment_call(client, db, mocks, monkeypatch):
    seen = {}
    real = mocks.disburse

    def spy(case_id, cnic, amount, key):
        seen["row"] = db.execute(select(Decision).where(Decision.idempotency_key == key)).scalars().first()  # visible to other sessions already
        return real(case_id, cnic, amount, key)

    mocks.disburse = spy
    approve(client)
    assert seen["row"] is not None and seen["row"].payment_status == "pending"


def test_no_payment_when_nothing_is_owed_or_rejected(client, db, mocks):
    assert client.post("/cases/case-0001/decide", json={"action": "reject", "reason": "she was paid in full"}, headers=auth(client, "officer")).status_code == 200
    assert mocks.disburse_keys == []
    assert client.post("/cases/case-0003/decide", json={"action": "reject", "reason": "x y z"}, headers=auth(client, "officer")).status_code == 409  # approved already


def test_fake_client_pays_once_per_key():
    PAYMENTS.clear()
    c = FakeMocksClient()
    a = c.disburse("case-1", "0000042101001", 4000, "case-1:dec-1")
    b = c.disburse("case-1", "0000042101001", 4000, "case-1:dec-1")
    other = c.disburse("case-2", "0000042101002", 4000, "case-2:dec-9")
    assert a["payment_ref"] == b["payment_ref"] and a["duplicate"] is False and b["duplicate"] is True
    assert other["payment_ref"] != a["payment_ref"] and len(PAYMENTS) == 2


class _Resp(httpx.Response):
    pass


def _resp(status, **kw):
    return httpx.Response(status, request=httpx.Request("POST", "http://mocks/x"), **kw)


def test_real_client_uses_payments_endpoint_when_it_exists(monkeypatch):
    sent = {}

    def post(url, **kw):
        sent.update(url=url, **kw)
        return _resp(200, json={"payment_ref": "PAY-REAL-1", "duplicate": True, "simulated": True})

    monkeypatch.setattr(httpx, "post", post)
    res = MocksClient("http://mocks:8001").disburse("case-1", "0000042101001", 4000, "case-1:dec-1")
    assert sent["url"] == "http://mocks:8001/payments/disburse" and sent["headers"]["Idempotency-Key"] == "case-1:dec-1"
    assert sent["json"] == {"case_id": "case-1", "cnic": "0000042101001", "amount_pkr": 4000, "idempotency_key": "case-1:dec-1"}
    assert res == {"payment_ref": "PAY-REAL-1", "via": "payments", "duplicate": True, "simulated": True}


def test_real_client_falls_back_to_complaints_on_404(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda url, **kw: _resp(404, json={"detail": "Not Found"}))
    seen = {}

    def request(method, url, **kw):
        seen.update(method=method, url=url, json=kw.get("json"))
        return _resp(200, json={"ticket_id": "TKT-ABC", "simulated": True})

    monkeypatch.setattr(httpx, "request", request)
    res = MocksClient("http://mocks:8001").disburse("case-1", "0000042101001", 4000, "case-1:dec-1")
    assert res["payment_ref"] == "TKT-ABC" and res["via"] == "complaints_fallback"
    assert seen["url"].endswith("/complaints") and seen["json"]["category"] == "payment_topup" and "case-1:dec-1" in seen["json"]["description"]


@pytest.mark.parametrize("failure", [lambda url, **kw: _resp(500), lambda url, **kw: (_ for _ in ()).throw(httpx.ConnectTimeout("slow"))])
def test_real_client_errors_become_mock_unavailable(monkeypatch, failure):
    monkeypatch.setattr(httpx, "post", failure)
    with pytest.raises(MockUnavailable):
        MocksClient("http://mocks:8001").disburse("c", "0000042101001", 1, "k")
