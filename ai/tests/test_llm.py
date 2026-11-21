"""llm.py: fail-safe client. The HTTP layer is faked: no test uses a real key or the network."""
import json
import logging
import urllib.error

import pytest

from bharosa_ai import llm

FAKE_KEY = "test-key-not-a-real-secret"


class FakeResponse:
    def __init__(self, body):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


def http_error(code):
    return urllib.error.HTTPError("https://api.x.ai/v1/chat/completions", code, "err", {}, None)


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("AI_USE_LLM", "1")
    monkeypatch.setenv("LLM_API_KEY", FAKE_KEY)
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)


def script(monkeypatch, *outcomes):
    """Fake urlopen: returns/raises the outcomes in order (the last one repeats) and records every call."""
    calls = []

    def fake(request, timeout=None):
        calls.append((request, timeout))
        out = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(out, Exception):
            raise out
        return FakeResponse(out)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    return calls


def test_status_says_why_it_is_off_and_never_shows_the_key(monkeypatch, on):
    assert llm.status() == "on" and llm.enabled()
    monkeypatch.setenv("AI_USE_LLM", "0")
    assert llm.status() == "off: AI_USE_LLM=0"
    monkeypatch.setenv("AI_USE_LLM", "1")
    monkeypatch.setenv("LLM_MODEL", "")
    assert llm.status() == "off: LLM_MODEL is not set"
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "")
    assert llm.status() == "off: LLM_API_KEY is not set"
    monkeypatch.setenv("LLM_API_KEY", FAKE_KEY)
    monkeypatch.setenv("LLM_BASE_URL", "http://insecure.example")
    assert not llm.enabled() and "https" in llm.status()
    assert FAKE_KEY not in llm.status()


def test_a_good_call_sends_the_expected_request(monkeypatch, on):
    calls = script(monkeypatch, reply('{"claim_type": "missing", "name": "Gul Bano"}'))
    assert llm.chat_json("system text", "user text") == {"claim_type": "missing", "name": "Gul Bano"}
    request, timeout = calls[0]
    body = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.x.ai/v1/chat/completions" and request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer " + FAKE_KEY and timeout == llm.TIMEOUT_SECONDS
    assert body["model"] == "test-model" and body["temperature"] == 0 and body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"] and FAKE_KEY not in json.dumps(body)


def test_custom_https_base_url_is_used(monkeypatch, on):
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1/")
    calls = script(monkeypatch, reply("{}"))
    llm.chat_json("s", "u")
    assert calls[0][0].full_url == "https://llm.example/v1/chat/completions"


@pytest.mark.parametrize("content,expected", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Here you go: {"a": 1} hope that helps', {"a": 1}),
    ("[1, 2]", None), ("no json at all", None), ("{broken", None), ("", None), (None, None), (5, None),
])
def test_reply_parsing(monkeypatch, on, content, expected):
    script(monkeypatch, reply(content))
    assert llm.chat_json("s", "u") == expected


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{}]}, {"choices": [{"message": {}}]}, [], "text", b"not json"])
def test_odd_response_shapes_give_none(monkeypatch, on, body):
    script(monkeypatch, body)
    assert llm.chat_json("s", "u") is None


def test_server_error_is_retried_once(monkeypatch, on):
    calls = script(monkeypatch, http_error(500), reply('{"ok": true}'))
    assert llm.chat_json("s", "u") == {"ok": True} and len(calls) == 2


def test_two_server_errors_or_timeouts_give_none(monkeypatch, on):
    calls = script(monkeypatch, http_error(503))
    assert llm.chat_json("s", "u") is None and len(calls) == 2
    calls = script(monkeypatch, TimeoutError("slow"))
    assert llm.chat_json("s", "u") is None and len(calls) == 2
    calls = script(monkeypatch, urllib.error.URLError("no network"))
    assert llm.chat_json("s", "u") is None and len(calls) == 2


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_are_not_retried(monkeypatch, on, code):
    calls = script(monkeypatch, http_error(code))
    assert llm.chat_json("s", "u") is None and len(calls) == 1


def test_rate_limit_is_retried(monkeypatch, on):
    calls = script(monkeypatch, http_error(429), reply('{"ok": 1}'))
    assert llm.chat_json("s", "u") == {"ok": 1} and len(calls) == 2


@pytest.mark.parametrize("name,value", [("AI_USE_LLM", "0"), ("LLM_API_KEY", ""), ("LLM_MODEL", ""), ("LLM_BASE_URL", "http://x.example")])
def test_off_means_no_network_call(monkeypatch, on, name, value):
    calls = script(monkeypatch, reply('{"a": 1}'))
    monkeypatch.setenv(name, value)
    assert llm.chat_json("s", "u") is None and calls == []


def _must_have_a(obj):
    if "a" not in obj:
        raise ValueError("missing a")
    return {"a": obj["a"]}


def test_validate_runs_on_the_reply_and_its_result_is_returned(monkeypatch, on):
    calls = script(monkeypatch, reply('{"a": 1, "extra": 2}'))
    assert llm.chat_json("s", "u", validate=_must_have_a) == {"a": 1} and len(calls) == 1


def test_an_invalid_reply_is_retried_once_with_the_bad_answer_and_a_hint(monkeypatch, on):
    calls = script(monkeypatch, reply('{"b": 1}'), reply('{"a": 2}'))
    assert llm.chat_json("s", "u", validate=_must_have_a, hint="answer with a") == {"a": 2} and len(calls) == 2
    second = json.loads(calls[1][0].data.decode("utf-8"))["messages"]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[2]["content"] == '{"b": 1}' and second[3]["content"] == "answer with a"


def test_not_json_counts_as_invalid_and_the_default_hint_is_used(monkeypatch, on):
    calls = script(monkeypatch, reply("no json here"), reply('{"a": 3}'))
    assert llm.chat_json("s", "u", validate=_must_have_a) == {"a": 3} and len(calls) == 2
    assert json.loads(calls[1][0].data.decode("utf-8"))["messages"][-1]["content"] == llm._DEFAULT_HINT


def test_invalid_twice_gives_none_and_never_a_third_call(monkeypatch, on):
    calls = script(monkeypatch, reply('{"b": 1}'), reply("still wrong"), reply('{"a": 9}'))
    assert llm.chat_json("s", "u", validate=_must_have_a) is None and len(calls) == 2


def test_a_network_failure_is_not_an_invalid_reply(monkeypatch, on):
    calls = script(monkeypatch, http_error(401))
    assert llm.chat_json("s", "u", validate=_must_have_a) is None and len(calls) == 1


def test_without_validate_a_bad_reply_is_not_retried(monkeypatch, on):
    calls = script(monkeypatch, reply("no json"), reply('{"a": 1}'))
    assert llm.chat_json("s", "u") is None and len(calls) == 1


def test_usage_counters_count_calls_and_tokens_and_hold_no_secret(monkeypatch, on):
    llm.reset_stats()
    script(monkeypatch, {"choices": [{"message": {"content": '{"a": 1}'}}], "usage": {"total_tokens": 120}})
    llm.chat_json("s", "u")
    script(monkeypatch, http_error(401))
    llm.chat_json("s", "u")
    s = llm.stats()
    assert s == {"calls": 2, "ok": 1, "tokens": 120} and FAKE_KEY not in repr(s)
    llm.reset_stats()
    assert llm.stats() == {"calls": 0, "ok": 0, "tokens": 0}


def test_nothing_secret_is_logged_or_raised(monkeypatch, on, caplog):
    script(monkeypatch, http_error(500), RuntimeError("boom " + FAKE_KEY))
    with caplog.at_level(logging.DEBUG):
        assert llm.chat_json("s", "u") is None
    assert FAKE_KEY not in caplog.text
