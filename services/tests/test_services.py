import time

import pytest
from fastapi.testclient import TestClient

from services import common
from services.main import app
from services.notifications import service as notif
from services.webhooks import service as hooks

KEY = {"X-Service-Key": "dev-services-key-not-for-production"}
CNIC = "0000042101002"
client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(common, "DELAYS", (0, 0, 0))
    monkeypatch.delenv("WEBHOOKS_ALLOW_LOCAL", raising=False)
    for store in (notif.CONSENT, notif.LOG, hooks.SUBS, hooks.LOG, common.JOBS, common.AUDIT):
        store.clear()


class Resp:
    def __init__(self, code=200):
        self.status_code = code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)


def flaky(fail_times, calls):
    def post(url, **kw):
        calls.append(kw)
        return Resp(500 if len(calls) <= fail_times else 200)
    return post


# ---- service key
@pytest.mark.parametrize("method,path", [("get", "/notifications"), ("get", "/jobs"), ("get", "/webhooks/subscriptions"),
                                         ("post", "/notifications/send"), ("post", "/events"), ("get", "/webhooks/deliveries")])
def test_endpoints_need_service_key(method, path):
    assert getattr(client, method)(path).status_code == 401
    assert getattr(client, method)(path, headers={"X-Service-Key": "wrong"}).status_code == 401
    assert client.get("/health").json()["simulated"] is True


# ---- notifications: consent is default-deny and checked before anything leaves
def test_no_consent_means_blocked_and_nothing_sent(monkeypatch):
    sent = []
    monkeypatch.setattr(notif, "_post", lambda to, text: sent.append(text) or "MSG-1")
    r = client.post("/notifications/send", headers=KEY, json={"cnic": CNIC, "to": "0300-0000000", "key": "case_approved"}).json()
    assert r["status"] == "blocked" and sent == []
    assert any(a["action"] == "notification.blocked" for a in common.AUDIT)


def test_consent_then_send_urdu_then_withdraw_blocks(monkeypatch):
    sent = []
    monkeypatch.setattr(notif, "_post", lambda to, text: sent.append(text) or "MSG-1")
    body = {"cnic": CNIC, "to": "0300-0000000", "key": "case_approved"}
    client.post("/notifications/consent", headers=KEY, json={"cnic": CNIC, "granted": True})
    ok = client.post("/notifications/send", headers=KEY, json=body).json()
    assert ok["status"] == "sent" and ok["message_id"] == "MSG-1" and "منظور" in sent[0]
    client.post("/notifications/consent", headers=KEY, json={"cnic": CNIC, "granted": False})
    assert client.post("/notifications/send", headers=KEY, json=body).json()["status"] == "blocked"
    assert len(sent) == 1
    assert [n["status"] for n in client.get("/notifications", headers=KEY, params={"cnic": CNIC}).json()["items"]] == ["sent", "blocked"]


def test_notification_retries_then_sends_or_goes_to_a_human(monkeypatch):
    notif.set_consent(CNIC, True)
    calls = []

    def post(to, text):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("mock down")
        return "MSG-2"
    monkeypatch.setattr(notif, "_post", post)
    r = notif.send(CNIC, "x", "with_officer", "en")
    assert r["status"] == "sent" and r["attempts"] == 3 and r["text"].startswith("Your case")
    monkeypatch.setattr(notif, "_post", lambda to, text: (_ for _ in ()).throw(RuntimeError("down")))
    r = notif.send(CNIC, "x", "with_officer")
    assert r["status"] == "failed" and r["attempts"] == 4  # bounded, never infinite
    assert common.JOBS[-1]["status"] == "dead"


def test_bad_input_is_rejected_calmly():
    notif.set_consent(CNIC, True)
    assert notif.send(CNIC, "x", "no_such_template")["status"] == "rejected"
    assert client.post("/notifications/send", headers=KEY, json={"cnic": "12", "to": "x", "key": "k"}).status_code == 422


# ---- webhooks: signing, replay, SSRF
def test_signature_verifies_and_rejects_tamper_wrong_secret_and_replay():
    body = b'{"event":"case.decided"}'
    h = hooks.sign("s3cret", int(time.time()), body)
    assert hooks.verify("s3cret", h, body)
    assert not hooks.verify("s3cret", h, body + b" ")
    assert not hooks.verify("other", h, body)
    assert not hooks.verify("s3cret", h, body, now=time.time() + 3600)  # old timestamp = replay
    assert not hooks.verify("s3cret", "garbage", body)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com", "http://127.0.0.1:9/x", "http://localhost/x",
                                 "http://169.254.169.254/latest", "http://10.0.0.5/x", "not a url"])
def test_ssrf_targets_refused(url):
    assert client.post("/webhooks/subscriptions", headers=KEY, json={"url": url, "events": ["case.decided"]}).status_code == 422


def test_local_target_allowed_only_with_demo_flag(monkeypatch):
    monkeypatch.setenv("WEBHOOKS_ALLOW_LOCAL", "1")
    assert hooks.safe_url("http://127.0.0.1:9000/hook") and not hooks.safe_url("file:///x")


def test_subscribe_validates_events_and_secret_is_shown_once(monkeypatch):
    monkeypatch.setenv("WEBHOOKS_ALLOW_LOCAL", "1")
    bad = client.post("/webhooks/subscriptions", headers=KEY, json={"url": "http://127.0.0.1:9/h", "events": ["nope"]})
    assert bad.status_code == 422
    ok = client.post("/webhooks/subscriptions", headers=KEY, json={"url": "http://127.0.0.1:9/h", "events": ["case.decided"]})
    assert ok.status_code == 201 and len(ok.json()["secret"]) > 20
    listed = client.get("/webhooks/subscriptions", headers=KEY).json()["items"]
    assert len(listed) == 1 and "secret" not in listed[0]
    assert client.delete("/webhooks/subscriptions/" + ok.json()["id"], headers=KEY).status_code == 200
    assert client.delete("/webhooks/subscriptions/nope", headers=KEY).status_code == 404


def _sub(monkeypatch, events=("case.status_changed",)):
    monkeypatch.setenv("WEBHOOKS_ALLOW_LOCAL", "1")
    return hooks.subscribe("http://127.0.0.1:9/h", list(events))


def test_delivery_is_signed_verifiable_and_fresh_each_try(monkeypatch):
    sub, calls = _sub(monkeypatch), []
    rec = hooks.deliver(sub, "case.status_changed", {"case_id": "c1"}, post=flaky(2, calls))
    assert rec["status"] == "delivered" and rec["attempts"] == 3
    last = calls[-1]
    assert hooks.verify(sub["secret"], last["headers"]["X-Bharosa-Signature"], last["content"])
    assert b'"simulated":true' in last["content"]


def test_failing_receiver_is_dead_lettered_after_bounded_retries(monkeypatch):
    sub, calls = _sub(monkeypatch), []
    rec = hooks.deliver(sub, "case.status_changed", {}, post=flaky(99, calls))
    assert rec["status"] == "dead" and rec["attempts"] == 4 == len(calls)
    assert hooks.LOG[-1]["status"] == "dead" and any(a["action"] == "webhook.dead" for a in common.AUDIT)


def test_events_endpoint_fans_out_only_to_matching_subscribers(monkeypatch):
    _sub(monkeypatch, ("case.status_changed",))
    _sub(monkeypatch, ("consent.withdrawn",))
    calls = []
    monkeypatch.setattr(hooks.httpx, "post", flaky(0, calls))
    r = client.post("/events", headers=KEY, json={"event": "case.status_changed", "payload": {"case_id": "c1"}})
    assert r.status_code == 202 and len(calls) == 1
    assert client.get("/webhooks/deliveries", headers=KEY).json()["items"][0]["status"] == "delivered"
    assert client.post("/events", headers=KEY, json={"event": "bogus"}).status_code == 422
    assert client.get("/jobs", headers=KEY).json()["items"][0]["status"] == "done"


def test_a_dead_subscriber_does_not_delay_the_others(monkeypatch):
    monkeypatch.setattr(common, "DELAYS", (0.4, 0.4, 0.4))  # the dead one takes ~1.2 s to give up
    dead = _sub(monkeypatch)
    _sub(monkeypatch)  # a healthy second subscriber
    started, delivered_at = time.time(), []

    def post(url, **kw):  # tell the subscribers apart by whose secret signed the request
        if hooks.verify(dead["secret"], kw["headers"]["X-Bharosa-Signature"], kw["content"]):
            return Resp(500)
        delivered_at.append(time.time() - started)
        return Resp(200)

    recs = hooks.dispatch("case.status_changed", {}, post=post)
    assert {r["status"] for r in recs} == {"dead", "delivered"}
    assert delivered_at[0] < 0.4  # the healthy subscriber got it at once, not after the dead one finished
