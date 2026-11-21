"""Data-quality tests and endpoint x chaos-switch contract tests."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import chaos
from app.main import app, IDENTITY, LEDGER
from contracts.schemas import ChaosState, PersonRecord

client = TestClient(app)
DATA = Path(__file__).resolve().parent.parent / "app" / "data"
CNIC = "0000042101001"


@pytest.fixture(autouse=True)
def _reset():
    chaos.reset()
    yield
    chaos.reset()


def test_people_count_and_fake_cnics():
    assert 50 <= len(IDENTITY) <= 100
    for cnic in IDENTITY:
        assert len(cnic) == 13 and cnic.isdigit() and cnic.startswith("00000")
    for p in IDENTITY.values():
        PersonRecord(**dict(p, simulated=True))


def test_ledger_keys_exist_in_identity_and_ids_unique():
    assert set(LEDGER) <= set(IDENTITY)
    ids = [pay["payment_id"] for pays in LEDGER.values() for pay in pays]
    assert len(ids) == len(set(ids))


def test_data_has_the_messy_cases():
    labels = json.loads((DATA / "labels.json").read_text(encoding="utf-8"))
    assert len(labels["bad_agents"]) == 3
    assert labels["duplicate_identities"] and labels["wrong_records"] and labels["duplicate_payments"]
    assert labels["missing_fields"] and labels["name_variants"]
    short_agents = {s["agent_id"] for s in labels["short_payments"]}
    # short payments cluster on the 3 bad agents (plus one legacy one-off by agent-017)
    assert short_agents - {"agent-017"} == set(labels["bad_agents"])
    assert all(s["paid_pkr"] < s["expected_pkr"] for s in labels["short_payments"])
    # duplicate identities share name and DOB with a different CNIC
    for d in labels["duplicate_identities"]:
        a, b = IDENTITY[d["cnic"]], IDENTITY[d["same_as"]]
        assert a["cnic"] != b["cnic"] and a["full_name"] == b["full_name"] and a["date_of_birth"] == b["date_of_birth"]


def test_original_five_records_unchanged():
    assert IDENTITY[CNIC]["full_name"] == "Muhammad Aslam"
    assert LEDGER[CNIC][0]["amount_pkr"] == 8000 and LEDGER["0000042101003"] == []


def test_official_sender_has_no_lookalike():
    s = client.get("/senders").json()["senders"]
    assert "9090" in s and "9O9O" not in s


ENDPOINTS = [
    ("get", "/identity/" + CNIC, None),
    ("get", "/ledger/" + CNIC, None),
    ("get", "/senders", None),
    ("post", "/complaints", {"cnic": CNIC, "category": "short_paid", "description": "x"}),
    ("post", "/notify", {"to": "0300-0000000", "message": "hi"}),
]


@pytest.mark.parametrize("switch", ["timeout", "error_500", "missing_record", "duplicate_payment", "lookalike_sender"])
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_every_endpoint_under_every_switch_is_safe(switch, method, path, body):
    client.post("/chaos", json={switch: True})
    r = getattr(client, method)(path, **({"json": body} if body else {}))
    assert r.status_code in (200, 404, 500, 504)
    j = r.json()
    assert j["simulated"] is True
    assert "Traceback" not in r.text
    if switch == "timeout":
        assert r.status_code == 504
    if switch == "error_500":
        assert r.status_code == 500


def test_presets():
    names = client.get("/chaos/presets").json()["presets"]
    assert {"bad_day", "identity_down", "slow_network", "scam_wave", "normal"} <= set(names)
    r = client.post("/chaos/preset/identity_down").json()
    ChaosState(**r)
    assert r["error_500"] is True and r["simulated"] is True
    assert client.get("/identity/" + CNIC).status_code == 500
    r = client.post("/chaos/preset/scam_wave").json()
    assert r["lookalike_sender"] is True and r["error_500"] is False  # preset replaces, not stacks
    assert client.post("/chaos/preset/nope").status_code == 404
    assert client.post("/chaos/preset/normal").json()["lookalike_sender"] is False


def test_chaos_token_guard(monkeypatch):
    monkeypatch.setenv("CHAOS_TOKEN", "s3cret")
    r = client.post("/chaos", json={"error_500": True})
    assert r.status_code == 403 and r.json()["simulated"] is True
    assert client.get("/chaos").status_code == 200  # reading stays open
    ok = client.post("/chaos", json={"error_500": True}, headers={"X-Chaos-Token": "s3cret"})
    assert ok.status_code == 200
    assert client.post("/chaos/reset", headers={"X-Chaos-Token": "s3cret"}).status_code == 200


def test_demo_people_from_shared_fixture_are_served():
    demo = json.loads((DATA.parent.parent.parent / "contracts" / "fixtures" / "demo_people.json").read_text(encoding="utf-8"))
    for person in demo["people"]:
        r = client.get("/identity/" + person["cnic"])
        assert r.status_code == 200 and r.json()["full_name"] == person["identity"]["full_name"]
        assert client.get("/ledger/" + person["cnic"]).json()["payments"] == person["payments"]
    assert set(demo["official_senders"]) <= set(client.get("/senders").json()["senders"])


def test_disburse_is_idempotent_and_simulated():
    body = {"case_id": "case-1", "cnic": CNIC, "amount_pkr": 4000}
    a = client.post("/payments/disburse", json=body, headers={"Idempotency-Key": "case-1:d1"}).json()
    b = client.post("/payments/disburse", json=body, headers={"Idempotency-Key": "case-1:d1"}).json()
    c = client.post("/payments/disburse", json=body, headers={"Idempotency-Key": "case-1:d2"}).json()
    assert a["simulated"] and a["duplicate"] is False and b["duplicate"] is True
    assert a["payment_ref"] == b["payment_ref"] != c["payment_ref"]


def test_disburse_rejects_bad_input_calmly():
    assert client.post("/payments/disburse", json={"case_id": "c", "cnic": CNIC, "amount_pkr": 1}).status_code == 422
    r = client.post("/payments/disburse", json={"case_id": "c", "cnic": CNIC, "amount_pkr": -5, "idempotency_key": "k"})
    assert r.status_code == 422 and r.json()["simulated"] is True
    r = client.post("/payments/disburse", json={"case_id": "c", "cnic": "0000000000000", "amount_pkr": 5, "idempotency_key": "k2"})
    assert r.status_code == 404 and r.json()["simulated"] is True


def test_disburse_under_chaos_and_reset():
    client.post("/chaos", json={"error_500": True})
    r = client.post("/payments/disburse", json={"case_id": "c", "cnic": CNIC, "amount_pkr": 5, "idempotency_key": "k3"})
    assert r.status_code == 500 and r.json()["simulated"] is True
    client.post("/reset")
    ok = client.post("/payments/disburse", json={"case_id": "c", "cnic": CNIC, "amount_pkr": 5, "idempotency_key": "k3"})
    assert ok.status_code == 200 and ok.json()["duplicate"] is False


def test_call_counter_and_reset():
    client.post("/reset")
    client.get("/ledger/" + CNIC)
    client.get("/ledger/" + CNIC)
    client.get("/health")
    c = client.get("/calls").json()
    assert c["calls"]["GET /ledger/" + CNIC] == 2 and c["simulated"] is True and not any("health" in k for k in c["calls"])
    client.post("/reset")
    assert "GET /ledger/" + CNIC not in client.get("/calls").json()["calls"]
