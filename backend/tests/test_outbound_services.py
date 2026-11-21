"""Notifications + webhooks wiring: consent-gated, signed by the services app, and a dead service never breaks the claim."""
import httpx
import pytest

from app.config import settings
from app.services import outbound
from tests.conftest import auth


class FakeServices:
    """Stands in for /services: records calls, can be switched to fail or hang."""

    def __init__(self):
        self.calls = []
        self.down = False

    def post(self, url, json=None, headers=None, timeout=None):
        if self.down:
            raise httpx.ConnectError("services are down")
        self.calls.append(("POST", url, json, headers))
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"ok": True}})()

    def get(self, url, params=None, headers=None, timeout=None):
        if self.down:
            raise httpx.ConnectError("services are down")
        items = [{"id": "N-1", "key": "with_officer", "status": "sent", "text_ur": "اردو", "text_en": "English", "at": 1}]
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"items": items}})()


@pytest.fixture()
def services(monkeypatch):
    fake = FakeServices()
    monkeypatch.setattr(settings, "NOTIFICATIONS_URL", "http://svc.test")
    monkeypatch.setattr(settings, "WEBHOOKS_URL", "http://svc.test")
    monkeypatch.setattr(outbound.httpx, "post", fake.post)
    monkeypatch.setattr(outbound.httpx, "get", fake.get)
    return fake


SPEECH = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def _claim(client, user):
    r = client.post("/claims", json=SPEECH, headers=auth(client, user))
    assert r.status_code == 202
    return client.get("/claims/%s" % r.json()["claim_id"], headers=auth(client, user)).json()


def test_status_change_creates_a_notification_with_consent_and_forwards_the_event(client, demo, services):
    c = _claim(client, "demo-live")
    assert c["status"] == "needs_more_proof"
    urls = [(u, body) for _, u, body, _ in services.calls]
    sends = [b for u, b in urls if u.endswith("/notifications/send")]
    assert sends and sends[-1]["key"] == "needs_more_proof" and sends[-1]["lang"] == "both" and sends[-1]["cnic"] == "0000042101108"
    assert any(u.endswith("/notifications/consent") and b == {"cnic": "0000042101108", "granted": True} for u, b in urls)
    events = [b for u, b in urls if u.endswith("/events")]
    assert events and events[-1]["event"] == "case.status_changed" and events[-1]["payload"]["to"] == "needs_more_proof"
    assert "cnic" not in str(events[-1]) and "name" not in events[-1]["payload"]  # ids and statuses only
    assert all(h.get("X-Service-Key") for _, _, _, h in services.calls)


def test_no_notifications_consent_means_no_message_and_no_call(client, demo, services):
    h = auth(client, "demo-live")
    notif = next(c for c in client.get("/consent", headers=h).json()["items"] if c["scope"] == "notifications")
    assert notif["granted"] is True  # seeded as granted
    assert client.post("/consent/%s/withdraw" % notif["id"], headers=h).status_code == 200
    assert next(c for c in client.get("/consent", headers=h).json()["items"] if c["scope"] == "notifications")["granted"] is False
    services.calls.clear()
    _claim(client, "demo-live")
    assert not [1 for _, u, _, _ in services.calls if "/notifications/" in u]  # consent withdrawn: nothing sent to the service
    assert any(u.endswith("/events") for _, u, _, _ in services.calls)  # the (id-only) webhook event still goes out


def test_a_dead_services_app_never_breaks_the_claim(client, demo, services):
    services.down = True
    c = _claim(client, "demo-live")  # 202 + a normal result, no 500
    assert c["status"] == "needs_more_proof" and all(s["status"] == "done" for s in c["pipeline_steps"])
    assert client.get("/me/notifications", headers=auth(client, "demo-live")).json() == {"items": []}  # the inbox degrades to empty


def test_my_notifications_are_mine_and_off_by_default(client, demo, services, monkeypatch):
    r = client.get("/me/notifications", headers=auth(client, "demo-live"))
    assert r.status_code == 200 and r.json()["items"][0]["text_en"] == "English" and r.json()["items"][0]["text_ur"]
    assert client.get("/me/notifications").status_code == 401
    assert client.get("/me/notifications", headers=auth(client, "officer")).status_code == 403
    monkeypatch.setattr(settings, "NOTIFICATIONS_URL", "")
    assert client.get("/me/notifications", headers=auth(client, "demo-live")).json() == {"items": []}


def test_with_no_urls_set_nothing_is_called(client, demo, monkeypatch):
    called = []
    monkeypatch.setattr(outbound.httpx, "post", lambda *a, **k: called.append(a))
    _claim(client, "demo-live")
    assert called == []
