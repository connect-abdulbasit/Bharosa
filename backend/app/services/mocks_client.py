"""HTTP client for /mocks. Callers must have checked consent first.

Failures (timeout, 5xx, 404) raise MockUnavailable; the pipeline turns them into a
`with_officer` case with notes, NEVER a 500 to the user.
"""
from typing import Any, Dict

import httpx

from app.config import settings
from app.fake_mocks_client import FakeMocksClient


class MockUnavailable(Exception):
    pass


class MocksClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, path: str, **kw: Any) -> Dict[str, Any]:
        try:
            r = httpx.request(method, self.base_url + path, timeout=self.timeout, **kw)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MockUnavailable("%s %s failed: %s" % (method, path, exc))

    def identity(self, cnic: str) -> Dict[str, Any]:
        return self._call("GET", "/identity/%s" % cnic)

    def ledger(self, cnic: str) -> Dict[str, Any]:
        return self._call("GET", "/ledger/%s" % cnic)

    def complaint(self, cnic: str, category: str, description: str) -> Dict[str, Any]:
        return self._call("POST", "/complaints", json={"cnic": cnic, "category": category, "description": description})

    def senders(self) -> Dict[str, Any]:
        return self._call("GET", "/senders")

    def notify(self, to: str, message: str, channel: str = "sms") -> Dict[str, Any]:
        return self._call("POST", "/notify", json={"to": to, "message": message, "channel": channel})


def get_mocks_client():
    if settings.MOCKS_URL:
        return MocksClient(settings.MOCKS_URL)
    return FakeMocksClient()
