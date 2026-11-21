"""E2E harness: public interfaces only (HTTP). Skips cleanly when the stack is not running.

Env: BASE (backend, default :8000), MOCKS_URL (default :8001), SERVICES_URL (default :8002).
Needs: backend with MOCKS_URL pointing at the real mocks, DEMO_MODE=1 (demo reset + 30/min login).
"""
import os
import time

import httpx
import pytest

BASE = os.environ.get("BASE", "http://localhost:8000").rstrip("/")
MOCKS = os.environ.get("MOCKS_URL", "http://localhost:8001").rstrip("/")
SERVICES = os.environ.get("SERVICES_URL", "http://localhost:8002").rstrip("/")
SERVICE_KEY = os.environ.get("SERVICES_API_KEY", "dev-services-key-not-for-production")
PASSWORDS = {"admin": "admin-demo-123", "officer": "officer-demo-123", "auditor": "auditor-demo-123", "helper": "helper-demo-123"}
SAY = {"transcript": "mujhe is mahine ke paisay nahi mile"}


def _names():
    """username -> the name that person says (contracts/fixtures/demo_people.json). The real extractor refuses speech with no name."""
    import json
    from pathlib import Path

    try:
        path = Path(__file__).resolve().parent.parent / "contracts" / "fixtures" / "demo_people.json"
        return {p["username"]: p["name"] for p in json.loads(path.read_text(encoding="utf-8"))["people"]}
    except (OSError, ValueError, KeyError):
        return {}


NAMES = _names()
_tokens: dict = {}


def up(url: str) -> bool:
    try:
        return httpx.get(url + "/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def pytest_collection_modifyitems(config, items):
    if not (up(BASE) and up(MOCKS)):
        skip = pytest.mark.skip(reason="stack not running (need backend %s and mocks %s)" % (BASE, MOCKS))
        for item in items:
            if "services" not in item.keywords:
                item.add_marker(skip)
    if not up(SERVICES):
        skip = pytest.mark.skip(reason="services not running at %s" % SERVICES)
        for item in items:
            if "services" in item.keywords:
                item.add_marker(skip)


def pytest_configure(config):
    config.addinivalue_line("markers", "services: needs the services app (notifications, webhooks)")


class Api:
    """Tiny HTTP helper: api("POST", "/claims", token, json=...) -> (status, json)."""

    def __call__(self, method, path, token=None, base=BASE, **kw):
        headers = dict(kw.pop("headers", {}), **({"Authorization": "Bearer " + token} if token else {}))
        r = httpx.request(method, base + path, headers=headers, timeout=60, **kw)
        return r.status_code, (r.json() if r.content else None)

    def login(self, user):
        if user not in _tokens:
            s, b = self("POST", "/auth/login", json={"username": user, "password": PASSWORDS.get(user, "citizen-demo-123")})
            assert s == 200, "login %s -> %s %s" % (user, s, b)
            _tokens[user] = b["access_token"]
        return _tokens[user]

    def claim(self, user, body=SAY):
        """File a claim as `user` and wait for the background pipeline to settle. Returns the full claim.
        A spoken claim starts with the person's name, so it passes with the stub AI and with AI_MODE=real (offline parser)."""
        tok = self.login(user)
        if "transcript" in body and user in NAMES:
            body = dict(body, transcript="mera naam %s hai. %s" % (NAMES[user], body["transcript"]))
        s, b = self("POST", "/claims", tok, json=body)
        assert s == 202, "POST /claims -> %s %s" % (s, b)
        return self.settle(tok, b["claim_id"])

    def settle(self, tok, claim_id):
        for _ in range(300):
            if not self("GET", "/claims/%s/progress" % claim_id, tok)[1]["active"]:
                break
            time.sleep(0.1)
        return self("GET", "/claims/%s" % claim_id, tok)[1]

    def audit(self, **q):
        return self("GET", "/audit", self.login("admin"), params=q)[1]

    def mocks_calls(self):
        return self("GET", "/calls", base=MOCKS)[1]["calls"]


@pytest.fixture(scope="session")
def api():
    return Api()


def _reset_all(api):
    api("POST", "/reset", base=MOCKS)  # chaos, call counts, payment keys
    assert api("POST", "/admin/demo/reset", api.login("admin"), json={"include_rules": True})[0] == 200


@pytest.fixture(autouse=True)
def clean(api):
    """Known state BEFORE every scenario (demo data, rule v1, no chaos, empty call log); chaos is cleared AFTER it too."""
    _reset_all(api)
    yield
    api("POST", "/reset", base=MOCKS)


@pytest.fixture(scope="session", autouse=True)
def leave_clean(api):
    yield
    _reset_all(api)  # the demo state (and rule v1) is restored at the end of the run
