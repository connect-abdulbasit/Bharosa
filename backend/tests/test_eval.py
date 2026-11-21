import json

import bharosa_ai
from app.config import settings
from contracts.ai_interface import ClaimDraft
from tests.conftest import auth

SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def strong(monkeypatch):
    monkeypatch.setattr(bharosa_ai, "extract_claim", lambda t: ClaimDraft(
        claimant_name="Mohammad Aslam", claim_type="missing", amount_claimed_pkr=12000, period="2026-10", confidence=0.97, model_version="t"))


def ev(client, who="officer"):
    return client.get("/eval", headers=auth(client, who))


def test_roles(client):
    for who in ("officer", "admin", "auditor"):
        assert ev(client, who).status_code == 200
    for who in ("citizen", "helper"):
        assert ev(client, who).status_code == 403
    assert client.get("/eval").status_code == 401


def test_seeded_counts_and_shape(client):
    b = ev(client).json()
    assert b["decisions"]["ai_total"] == 4 and b["decisions"]["by_action"] == {"send_to_human": 1, "ask_more": 1, "auto_handle": 2}
    assert b["decisions"]["by_rule_version"] == {"rule-stipend-short-payment v1": 4}
    assert 0.0 < b["confidence"]["ai_average"] < 1.0 and set(b["confidence"]["by_action"]) == {"send_to_human", "ask_more", "auto_handle"}
    assert b["officer_vs_ai"] == {"compared": 0, "overrides": 0, "override_rate": None, "pairs": {}}  # nothing to compare yet
    assert b["messages"]["total"] == 0 and "model_eval" not in b and b["pipeline"]["runs"] == 0


def test_counts_overrides_confidence_and_pipeline_time(client, mocks, monkeypatch):
    strong(monkeypatch)
    c6, c7, c8 = (client.post("/claims", json=SPEECH, headers=auth(client, "citizen0%d" % n)).json() for n in (6, 7, 8))
    assert c6["decision"]["action"] == "auto_handle" and c6["status"] == "with_officer"
    off = auth(client, "officer")
    client.post("/cases/%s/decide" % c6["case_id"], json={"action": "approve", "reason": "agree with the AI"}, headers=off)
    client.post("/cases/%s/decide" % c7["case_id"], json={"action": "reject", "reason": "the AI was too keen"}, headers=off)  # override
    client.post("/cases/%s/decide" % c8["case_id"], json={"action": "ask_more", "reason": "photo needed"}, headers=off)        # override
    b = ev(client, "auditor").json()
    assert b["decisions"]["ai_total"] == 4 + 3 and b["decisions"]["by_action"]["auto_handle"] == 2 + 3
    assert b["decisions"]["officer_total"] == 3 and b["decisions"]["officer_by_action"] == {"approve": 1, "reject": 1, "ask_more": 1}
    assert b["officer_vs_ai"]["compared"] == 3 and b["officer_vs_ai"]["overrides"] == 2 and b["officer_vs_ai"]["override_rate"] == 0.667
    assert b["officer_vs_ai"]["pairs"] == {"auto_handle -> approve": 1, "auto_handle -> reject": 1, "auto_handle -> ask_more": 1}
    assert b["pipeline"]["runs"] == 3 and b["pipeline"]["average_seconds"] >= 0 and b["pipeline"]["max_seconds"] >= b["pipeline"]["average_seconds"]
    assert b["confidence"]["by_action"]["auto_handle"] > 0.9


def test_scam_check_totals(client, mocks):
    h = auth(client, "citizen")
    client.post("/messages/check", json={"text": "Pay fee at http://bit.ly/x urgent", "sender": "SAHARA-INFO"}, headers=h)
    client.post("/messages/check", json={"text": "Your stipend is ready", "sender": "9090"}, headers=h)
    client.post("/messages/check", json={"text": "Your stipend is ready", "sender": "9O9O"}, headers=h)
    m = ev(client).json()["messages"]
    assert m["total"] == 3 and m["by_label"] == {"scam": 2, "genuine": 1} and 0.9 < m["average_confidence"] <= 1.0


def test_model_eval_file_is_included_when_present(client, tmp_path, monkeypatch):
    f = tmp_path / "eval_results.json"
    f.write_text(json.dumps({"model_version": "ali-1", "classifier": {"accuracy": 0.94}}))
    monkeypatch.setattr(settings, "EVAL_RESULTS_PATH", f)
    assert ev(client).json()["model_eval"] == {"model_version": "ali-1", "classifier": {"accuracy": 0.94}}
    f.write_text("{not json")  # a broken file must not break the endpoint
    r = ev(client)
    assert r.status_code == 200 and "model_eval" not in r.json()
