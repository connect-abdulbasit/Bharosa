import pytest
from sqlalchemy import select

from app.models import AuditLog, RuleVersion
from app.services import jsonlogic
from app.services.rules import DEFAULT_LOGIC
from tests.conftest import auth

URL = "/rules/rule-stipend-short-payment/versions"
BASE = {"auto_handle_min": 0.9, "ask_more_min": 0.6}


def publish(client, **kw):
    return client.post(URL, json=dict(BASE, **kw), headers=auth(client, "admin"))


def test_default_rule_is_valid_and_evaluates():
    jsonlogic.validate_logic(DEFAULT_LOGIC)
    ev = jsonlogic.evaluate
    assert ev(DEFAULT_LOGIC, {"confidence": 0.95, "red_flags": []}) == "auto_handle"
    assert ev(DEFAULT_LOGIC, {"confidence": 0.95, "red_flags": ["x"]}) == "ask_more"  # flags never auto-handle
    assert ev(DEFAULT_LOGIC, {"confidence": 0.7, "red_flags": []}) == "ask_more"
    assert ev(DEFAULT_LOGIC, {"confidence": 0.2, "red_flags": []}) == "send_to_human"


@pytest.mark.parametrize("logic,fragment", [
    ({"eval": ["1+1"]}, "Unknown operator 'eval'"),
    ({"if": [{"var": "secret"}, "auto_handle", "send_to_human"]}, "Unknown variable 'secret'"),
    ({"==": [1, 1], "or": []}, "exactly one operator"),
    ({"if": [True, "auto_handle"]}, "'if' needs"),
    ({"if": [{">=": [{"var": "confidence"}, 0.5]}, "yes", "no"]}, "must always return one of"),
    ("auto_handle", "json-logic object"),
    ({"if": [True, "auto_handle", "auto_handle"]}, "Unsafe rule"),
    ({"if": [{">=": [{"var": "confidence"}, 0.3]}, "auto_handle", "send_to_human"]}, "Unsafe rule"),
    ({"if": [{">": [{"var": "confidence"}, 0.8]}, "auto_handle", "ask_more"]}, "red flags"),
])
def test_invalid_logic_is_rejected_with_a_clear_message(logic, fragment):
    with pytest.raises(jsonlogic.RuleError) as e:
        jsonlogic.validate_logic(logic)
    assert fragment in str(e.value)


def test_too_deep_and_too_big_are_rejected():
    deep = "auto_handle"
    for _ in range(12):
        deep = {"if": [True, deep, "send_to_human"]}
    with pytest.raises(jsonlogic.RuleError, match="deeply"):
        jsonlogic.validate_logic(deep)
    with pytest.raises(jsonlogic.RuleError, match="too large"):
        jsonlogic.validate_logic({"and": [{"==": [1, 1]}] * 100})


def test_api_rejects_invalid_rule_saves_nothing_and_audits(client, db):
    r = publish(client, logic={"if": [True, "auto_handle", "auto_handle"]})
    assert r.status_code == 422 and "Unsafe rule" in r.json()["message"]
    assert db.query(RuleVersion).count() == 1  # still only v1
    assert client.get("/rules", headers=auth(client, "admin")).json()["items"][0]["current_version"] == 1
    assert db.execute(select(AuditLog).where(AuditLog.action == "rule.rejected")).scalars().first() is not None


@pytest.mark.parametrize("body", [
    {"auto_handle_min": 0.5, "ask_more_min": 0.8},
    {"auto_handle_min": 1.5, "ask_more_min": 0.5},
    {"auto_handle_min": 0.4, "ask_more_min": 0.2},
    {"red_flags": ["x"] * 31},
    {"red_flags": [""]},
])
def test_api_rejects_bad_thresholds(client, body):
    assert publish(client, **body).status_code == 422


def test_valid_new_version_is_active_immediately_and_old_stays(client):
    good = {"if": [{"and": [{">=": [{"var": "confidence"}, 0.95]}, {"==": [{"var": "red_flags.length"}, 0]}]}, "auto_handle",
                   {"if": [{">=": [{"var": "confidence"}, 0.7]}, "ask_more", "send_to_human"]}]}
    r = publish(client, auto_handle_min=0.95, ask_more_min=0.7, logic=good, note="stricter")
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["logic"] == good
    vs = client.get(URL, headers=auth(client, "officer")).json()["versions"]
    assert [v["version"] for v in vs] == [2, 1] and vs[1]["auto_handle_min"] == 0.9 and vs[1]["logic"] == DEFAULT_LOGIC


def test_empty_logic_keeps_the_previous_logic(client):
    assert publish(client, auto_handle_min=0.92).json()["logic"] == DEFAULT_LOGIC
