"""HTTP client for /mocks. Callers must have checked consent first.

get_mocks_client(): the real mocks when MOCKS_URL is set AND reachable, otherwise the in-process fake client.
Failures (timeout, 5xx, 404) raise MockUnavailable; the pipeline turns them into a `with_officer` case
with notes, NEVER a 500 to the user.
"""
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.config import settings
from app.fake_mocks_client import FakeMocksClient
from app.services.mock_errors import MockUnavailable

log = logging.getLogger("bharosa.mocks")
__all__ = ["MockUnavailable", "MocksClient", "get_mocks_client"]


class MocksClient:
    name = "real"

    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call(self, method: str, path: str, **kw: Any) -> Dict[str, Any]:
        try:
            r = httpx.request(method, self.base_url + path, timeout=self.timeout, **kw)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MockUnavailable("%s %s failed: %s" % (method, path, (str(exc).splitlines() or ["error"])[0]))

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


_probe: Tuple[float, Optional[bool]] = (0.0, None)


def _reachable(url: str) -> bool:
    """/health is never affected by chaos switches, so this only detects a mocks service that is not running."""
    global _probe
    now = time.time()
    if _probe[1] is not None and now - _probe[0] < 10:
        return bool(_probe[1])
    try:
        httpx.get(url.rstrip("/") + "/health", timeout=1.0).raise_for_status()
        ok = True
    except (httpx.HTTPError, ValueError):
        ok = False
    _probe = (now, ok)
    return ok


def get_mocks_client():
    if settings.MOCKS_URL:
        if _reachable(settings.MOCKS_URL):
            return MocksClient(settings.MOCKS_URL)
        log.warning("MOCKS_URL=%s is unreachable: using the in-process fake mocks client", settings.MOCKS_URL)
    return FakeMocksClient()
