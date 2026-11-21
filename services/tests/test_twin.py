import json

import httpx
import pytest

from services.digital_twin import twin
from services.digital_twin.twin import Twin, assess, score_wave

PROPOSED = {"auto_handle_min": 0.8, "ask_more_min": 0.6, "red_flags": ["short_payment"]}


def sim(by_transition, simulated=7, skipped=0):
    return {"proposed": PROPOSED, "current_version": 1, "simulated_cases": simulated, "skipped_no_inputs": skipped,
            "would_change": sum(by_transition.values()), "by_transition": by_transition, "examples": []}


def test_loosening_is_flagged_for_review():
    a = assess(sim({"ask_more -> auto_handle": 3, "send_to_human -> ask_more": 1}))
    assert a["less_human_oversight"] == 4 and a["more_human_oversight"] == 0 and a["verdict"].startswith("REVIEW")


def test_tightening_only_adds_workload():
    a = assess(sim({"ask_more -> send_to_human": 2, "auto_handle -> ask_more": 1}))
    assert a["less_human_oversight"] == 0 and a["more_human_oversight"] == 3 and a["verdict"].startswith("TIGHTER")


def test_no_change_and_no_data_are_distinguished():
    assert assess(sim({})).get("verdict").startswith("SAFE")
    assert assess(sim({}, simulated=0, skipped=5))["verdict"].startswith("NO DATA")  # never claim "safe" with nothing replayed


def test_scam_wave_scoring_is_honest_about_unsure():
    r = score_wave([{"truth": "scam", "label": "scam"}, {"truth": "scam", "label": "unsure"}, {"truth": "scam", "label": "genuine"},
                    {"truth": "genuine", "label": "scam"}, {"truth": "genuine", "label": "genuine"}, {"truth": "genuine", "label": "unsure"}])
    assert (r["scams_caught"], r["scams_unsure"], r["scams_missed"]) == (1, 1, 1)
    assert (r["genuine_blocked_by_mistake"], r["genuine_unsure"]) == (1, 1)


def test_wave_data_is_fictional_and_balanced():
    assert {t for _, _, t in twin.WAVE} == {"scam", "genuine"}
    assert all(s != "9090" for s, _, t in twin.WAVE if t == "scam")  # a scam never comes from the official code


def test_preview_calls_only_the_read_only_simulate_endpoint():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/rules":
            return httpx.Response(200, json={"items": [{"id": "rule-1"}]})
        return httpx.Response(200, json=dict(sim({"ask_more -> auto_handle": 1}), rule_id="rule-1"))

    t = Twin("http://x")
    t.http, t.tokens = httpx.Client(transport=httpx.MockTransport(handler)), {"admin": "tok"}
    out = t.preview("admin", 0.8, 0.6)
    assert calls == [("GET", "/rules"), ("POST", "/rules/rule-1/simulate")]  # never POST /rules/{id}/versions (publish)
    assert out["less_human_oversight"] == 1 and json.dumps(out)


def test_api_errors_surface_clearly():
    t = Twin("http://x")
    t.http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"error": "forbidden"})))
    with pytest.raises(RuntimeError, match="403"):
        t.call("GET", "/rules")
