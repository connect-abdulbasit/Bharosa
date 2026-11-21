import pytest
from fastapi.testclient import TestClient

from app import chaos
from app.main import app
from contracts.schemas import (ChaosState, ComplaintResponse, LedgerResponse, NotifyResponse,
                               PersonRecord, SendersResponse)

client = TestClient(app)
CNIC = "0000042101001"


@pytest.fixture(autouse=True)
def _reset():
    chaos.reset()
    yield
    chaos.reset()


def test_identity_ledger_senders_match_contract():
    r = client.get("/identity/" + CNIC)
    assert r.status_code == 200 and r.json()["simulated"] is True
    PersonRecord(**r.json())
    LedgerResponse(**client.get("/ledger/" + CNIC).json())
    s = client.get("/senders").json()
    SendersResponse(**s)
    assert "9090" in s["senders"] and s["simulated"] is True


def test_complaint_and_notify():
    c = client.post("/complaints", json={"cnic": CNIC, "category": "short_paid", "description": "x"}).json()
    ComplaintResponse(**c)
    n = client.post("/notify", json={"to": "0300-0000000", "message": "hi"}).json()
    NotifyResponse(**n)


def test_all_seed_records_work():
    for cnic in ["0000042101001", "0000042101002", "0000042101003", "0000042101004", "0000042101005"]:
        assert client.get("/identity/" + cnic).status_code == 200
        assert client.get("/ledger/" + cnic).status_code == 200


def test_unknown_record_404_with_simulated_flag():
    r = client.get("/identity/0000000000000")
    assert r.status_code == 404 and r.json()["simulated"] is True


def test_chaos_missing_record():
    client.post("/chaos", json={"missing_record": True})
    assert client.get("/identity/" + CNIC).status_code == 404
    assert client.get("/ledger/" + CNIC).status_code == 404


def test_chaos_error_and_timeout():
    client.post("/chaos", json={"error_500": True})
    r = client.get("/identity/" + CNIC)
    assert r.status_code == 500 and r.json()["simulated"] is True
    client.post("/chaos", json={"error_500": False, "timeout": True})
    assert client.get("/identity/" + CNIC).status_code == 504


def test_chaos_duplicate_payment():
    base = len(client.get("/ledger/" + CNIC).json()["payments"])
    client.post("/chaos", json={"duplicate_payment": True})
    assert len(client.get("/ledger/" + CNIC).json()["payments"]) == base + 1


def test_chaos_lookalike_sender():
    before = client.get("/senders").json()["senders"]
    client.post("/chaos", json={"lookalike_sender": True})
    after = client.get("/senders").json()["senders"]
    assert len(after) > len(before)


def test_chaos_slow_network():
    import time
    client.post("/chaos", json={"slow_network_ms": 150})
    t = time.time()
    client.get("/senders")
    assert time.time() - t >= 0.14


def test_chaos_reset_and_state():
    client.post("/chaos", json={"error_500": True, "slow_network_ms": 5})
    state = client.get("/chaos").json()
    ChaosState(**state)
    assert state["error_500"] is True
    reset = client.post("/chaos/reset").json()
    assert reset["error_500"] is False and reset["slow_network_ms"] == 0 and reset["simulated"] is True
    assert client.get("/identity/" + CNIC).status_code == 200


def test_ledger_down_breaks_only_the_ledger():
    """The Chaos Panel's "payment record down": identity, senders and notify keep working, the ledger answers 503."""
    client.post("/chaos/reset")
    assert client.post("/chaos", json={"ledger_down": True}).json()["ledger_down"] is True
    assert client.get("/ledger/0000042101001").status_code == 503
    assert client.get("/ledger/0000042101001").json()["simulated"] is True
    assert client.get("/identity/0000042101001").status_code == 200
    assert client.get("/senders").status_code == 200
    client.post("/chaos/reset")
    assert client.get("/ledger/0000042101001").status_code == 200
